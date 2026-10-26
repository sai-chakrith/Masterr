"""Synthetic approved fixtures; no real reviewer or provider calls are fabricated."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api import create_app
from backend.auth import Settings
from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningError
from backend.models import Assignment, Attempt, Learner, LearningSession, Question
from backend.numbers.bank import load_questions
from backend.retrieval import get_topic_notes
from backend.tutor import (IDK_ANSWER, NEXT_LINE, TutorService, TutorSettings,
                           answer_matches, select_mistakes)
from backend.tutor_models import PersonalExplanation, TopicLesson, TutoringRecord


@pytest.fixture
def engine(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "tutor.db"))
    Base.metadata.create_all(engine)
    with transaction(engine) as db:
        db.add_all([Learner(id="alice"), Learner(id="bob")])
    yield engine
    engine.dispose()


def missed(engine, owner="alice", suffix="1", source="diagnostic", level=3,
           hidden=False, status="completed", dont_know=False):
    item = copy.deepcopy(load_questions()[3])
    item.update(id="tutor-" + suffix, family_id="tutor-family-" + suffix,
                review_status="approved", review={"reviewer": "synthetic-test", "date": "test-only"},
                difficulty_level=level, hidden=hidden)
    qid, sid = item["id"] + "@1", "session-" + suffix
    with transaction(engine) as db:
        import_questions(db, [item])
        db.add(LearningSession(id=sid, learner_id=owner, skill_id="divisibility",
                               mode="diagnostic", policy_version="test-only", status=status,
                               created_at="2026-10-27T00:00:00+00:00"))
        db.flush()
        db.add(Assignment(id="assignment-" + suffix, session_id=sid, question_id=qid,
                          position=0, status="submitted", hint_count=0, solution_seen=False))
        db.flush()
        db.add(Attempt(id="attempt-" + suffix, learner_id=owner, assignment_id="assignment-" + suffix,
                       idempotency_key=suffix, request_hash="x" * 64, source=source,
                       dont_know=dont_know, raw_answer=IDK_ANSWER if dont_know else "999",
                       normalized_answer=0 if dont_know else 999, working="private working",
                       correct=False, assistance="independent", created_at="2026-10-27T00:00:00+00:00",
                       response={}))
    return qid


def response(text="A lesson from the notes.", finish="stop"):
    return {"model": "openai/gpt-oss-120b", "choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                      "prompt_tokens_details": {"cached_tokens": 32},
                      "completion_tokens_details": {"reasoning_tokens": 20}}}


class Provider:
    def __init__(self, wrong=False):
        self.calls = []
        self.wrong = wrong

    def __call__(self, payload, key):
        self.calls.append(payload)
        data = json.loads(payload["messages"][1]["content"])
        if "questions" in data:
            return response(json.dumps({"examples": [
                {"question_id": q["question_id"], "explanation": "Check both conditions.",
                 "answer": "123456" if self.wrong else q["correct_answer"]} for q in data["questions"]]}))
        return response()


def service(engine, provider=None, notes=None, **settings):
    return TutorService(engine, TutorSettings(api_key="test-key", **settings),
                        completion=provider or Provider(), notes=notes or (lambda topic: "Check both 2 and 3 for divisibility by 6."))


@pytest.mark.parametrize("candidate,correct,expected", [
    ("4", "4", True), ("4.0", "4", True), ("1/2", "0.5", True),
    ("1,000", "1000", True), ("50%", "50 %", True), ("50", "50%", False),
    ("2:4", "1:2", True), ("0.5", "1:2", False), ("4 cm", "4 cm", True),
    ("4 m", "4 cm", False), ("14", "4", False), ("4 or 5", "4", False),
    ("not all", "all", False), ("Option A", "A", False), ("TRUE", "true", True),
    ("1/0", "0", False), ("", "", False), ("Answer: 4", "4", False),
])
def test_answer_matches(candidate, correct, expected):
    assert answer_matches(candidate, correct) is expected


def test_all_current_bank_answers_and_distractors():
    for item in load_questions():
        assert answer_matches(str(item["answer"]), str(item["answer"]))
        for option in item.get("options", []):
            assert answer_matches(str(option["value"]), str(item["answer"])) == (option["value"] == item["answer"])


def test_selection_idk_then_nearest_level():
    items = [{"question_id": str(i), "level": i, "learner_answer": IDK_ANSWER if i == 1 else "9"} for i in range(1, 6)]
    assert [q["level"] for q in select_mistakes(items)] == [1, 3, 2]


def test_settings_and_real_usage_fields(engine):
    missed(engine)
    provider = Provider()
    result = service(engine, provider).tutor("alice", "divisibility")
    for call in provider.calls:
        assert call["reasoning_effort"] == "low" and call["include_reasoning"] is False
        assert call["max_completion_tokens"] == 2000
        assert "private working" not in json.dumps(call)
        assert "alice" not in json.dumps(call)
    assert result["parts"]["personal"]["examples"][0]["answer_checked"]
    assert result["usage"][0]["cached_prompt_tokens"] == 32
    assert result["usage"][0]["reasoning_tokens"] == 20
    with transaction(engine) as db:
        record = db.get(TutoringRecord, result["id"])
        assert record.usage == result["usage"] and record.prompt_version == result["prompt_version"]


@pytest.mark.parametrize("first", [response(""), response("cut off", "length")])
def test_retry_on_empty_or_length(engine, first):
    calls, usage = [], []
    def provider(payload, key):
        calls.append(payload)
        return first if len(calls) == 1 else response()
    text = service(engine, provider)._call_llm("system", {}, "lesson", usage)
    assert text and len(calls) == 2 and len(usage) == 2


def test_empty_twice_and_exception_fall_back_without_cache(engine):
    for provider in (lambda *args: response(""), lambda *args: (_ for _ in ()).throw(RuntimeError("secret"))):
        result = service(engine, provider).tutor("alice", "divisibility")
        assert result["parts"]["lesson"]["generated_by"] == "fallback"
        assert "secret" not in json.dumps(result)
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(TopicLesson)) == 0


def test_both_caches_notes_edits_model_and_effort_invalidate(engine):
    missed(engine)
    provider = Provider()
    tutor = service(engine, provider)
    tutor.tutor("alice", "divisibility")
    result = tutor.tutor("alice", "divisibility")
    assert len(provider.calls) == 2 and result["usage"] == []
    assert all(p["cached"] for p in result["parts"].values())
    tutor.notes = lambda topic: "Edited notes."
    tutor.tutor("alice", "divisibility")
    assert len(provider.calls) == 4
    service(engine, provider, model="another-model").tutor("alice", "divisibility")
    service(engine, provider, reasoning_effort="high").tutor("alice", "divisibility")
    assert len(provider.calls) == 8


def test_changed_answer_invalidates_personal_only(engine):
    missed(engine)
    provider = Provider()
    tutor = service(engine, provider)
    tutor.tutor("alice", "divisibility")
    with transaction(engine) as db:
        db.get(Attempt, "attempt-1").raw_answer = "998"
    result = tutor.tutor("alice", "divisibility")
    assert len(provider.calls) == 3 and result["parts"]["lesson"]["cached"]
    assert not result["parts"]["personal"]["cached"]


def test_wrong_example_regenerated_once_then_entire_working_removed(engine):
    missed(engine)
    provider = Provider(wrong=True)
    result = service(engine, provider).tutor("alice", "divisibility")
    personal = result["parts"]["personal"]
    assert len(provider.calls) == 3  # lesson plus two personal responses
    assert personal["generated_by"] == "fallback" and personal["examples"] == []
    assert "123456" not in result["content"] and "Check both conditions." not in personal["text"]
    assert "Correct answer:" in personal["text"]
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(PersonalExplanation)) == 0


def test_wrong_then_correct_example(engine):
    missed(engine)
    provider = Provider(wrong=True)
    def recovering(payload, key):
        if len(provider.calls) == 2:
            provider.wrong = False
        return provider(payload, key)
    result = service(engine, recovering).tutor("alice", "divisibility")
    assert len(provider.calls) == 3 and result["parts"]["personal"]["examples"][0]["answer_checked"]


def test_no_key_fallback_is_labelled_not_cached_and_has_next(engine):
    missed(engine, dont_know=True)
    tutor = TutorService(engine, TutorSettings(), notes=lambda topic: "Approved notes.")
    result = tutor.tutor("alice", "divisibility")
    assert result["usage"] == [] and result["generated_by"] == "fallback"
    assert result["lesson"].startswith("From the notes")
    assert IDK_ANSWER in result["personal"] and result["content"].endswith(NEXT_LINE)
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(TopicLesson)) == 0
        assert db.scalar(select(func.count()).select_from(PersonalExplanation)) == 0


def test_missing_notes_make_no_call(engine):
    provider = Provider()
    tutor = TutorService(engine, TutorSettings(api_key="test"), provider, notes=lambda topic: "")
    result = tutor.tutor("alice", "divisibility")
    assert not provider.calls and "not yet available" in result["lesson"]


def test_isolation_and_hidden_validation_exclusion(engine):
    public = missed(engine)
    missed(engine, "bob", "2")
    missed(engine, suffix="3", hidden=True)
    missed(engine, suffix="4", source="validation")
    tutor = service(engine)
    result = tutor.tutor("alice", "divisibility")
    assert result["selected_question_ids"] == [public]
    bob = tutor.tutor("bob", "divisibility")
    assert bob["parts"]["lesson"]["cached"] and not bob["parts"]["personal"]["cached"]
    assert public not in bob["selected_question_ids"]


def test_active_sessions_and_withdrawn_questions(engine):
    missed(engine, status="active")
    with pytest.raises(LearningError, match="Finish or abandon"):
        service(engine).tutor("alice", "divisibility")
    with transaction(engine) as db:
        db.get(LearningSession, "session-1").status = "completed"
        db.get(Question, "tutor-1@1").status = "withdrawn"
    assert service(engine).tutor("alice", "divisibility")["selected_question_ids"] == []


def test_notes_whole_file_hash_bound_review_and_path_safety(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.retrieval.load_curriculum", lambda: {"status": "draft", "skills": []})
    path = tmp_path / "divisibility.md"
    path.write_text("Topic-only notes.\n\nAll paragraphs.", encoding="utf-8")
    assert get_topic_notes("divisibility", tmp_path) == ""
    review = {"status": "approved", "reviewer": "synthetic-test", "date": "test-only",
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix(".review.json").write_text(json.dumps(review))
    assert get_topic_notes("divisibility", tmp_path) == path.read_text()
    path.write_text("Edited after review.")
    assert get_topic_notes("divisibility", tmp_path) == ""
    assert get_topic_notes("../divisibility", tmp_path) == ""


def test_api_auth_fallback_and_cached_reopen(engine):
    settings = Settings(database_url="", local_development=True, local_token="t" * 32)
    app = create_app(engine, settings)
    provider = Provider()
    app.state.tutor = service(engine, provider)
    headers = {"Authorization": "Bearer " + "t" * 32}
    with TestClient(app) as client:
        assert client.post("/v1/me/tutor/divisibility").status_code == 401
        assert client.get("/v1/me/tutor/topics", headers=headers).status_code == 200
        missed(engine, owner="local-developer", suffix="api")
        first = client.post("/v1/me/tutor/divisibility", headers=headers)
        assert first.status_code == 200 and first.json()["usage"]
        second = client.post("/v1/me/tutor/divisibility", headers=headers).json()
        assert second["usage"] == [] and all(p["cached"] for p in second["parts"].values())
        assert client.post("/v1/me/tutor/nonexistent", headers=headers).status_code == 404
        assert client.post("/v1/me/tutor/divisibility", headers={"Authorization": "Bearer wrong"}).status_code == 401


@pytest.mark.parametrize("settings", [{"reasoning_effort": "unlimited"}, {"max_completion_tokens": 1}])
def test_invalid_settings(settings):
    with pytest.raises(ValueError):
        TutorSettings(**settings)
