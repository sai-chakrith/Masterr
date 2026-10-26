"""Application integration uses synthetic content and fake provider boundaries only."""
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api import create_app
from backend.app_models import ContentDocument, DeletedIdentity, ReviewEvent
from backend.auth import Settings
from backend.content import available_questions, import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningService
from backend.models import Learner, Question
from backend.numbers.bank import load_questions
from backend.operations import AccountService, BudgetService
from backend.publication import topic_notes
from backend.tutor import TutorService, TutorSettings

TOKEN = "t" * 32
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def app_setup(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "app.db"))
    Base.metadata.create_all(engine)
    settings = Settings(database_url="", local_development=True, local_token=TOKEN,
                        admin_subjects=("local-developer",))
    app = create_app(engine, settings)
    with transaction(engine) as db:
        draft = copy.deepcopy(load_questions()[3])
        import_questions(db, [draft])
    with TestClient(app) as client:
        yield app, client, engine, draft["id"] + "@1"
    engine.dispose()


def publish_question(client, qid):
    old = client.get("/v1/admin/questions/" + qid, headers=AUTH).json()
    response = client.post("/v1/admin/questions/" + qid, headers=AUTH,
        json={"action": "approve", "expected_checksum": old["checksum"], "confirm_reviewed": True})
    assert response.status_code == 200, response.text
    return response.json()


def publish_document(client, key, document=None):
    route = "/v1/admin/documents/" + key
    old = client.get(route, headers=AUTH).json()
    if document is not None:
        result = client.post(route, headers=AUTH, json={"action": "save", "expected_checksum": old["checksum"], "document": document})
        assert result.status_code == 200, result.text
        old = result.json()
    result = client.post(route, headers=AUTH, json={"action": "approve", "expected_checksum": old["checksum"], "confirm_reviewed": True})
    assert result.status_code == 200, result.text
    return result.json()


def test_reviewer_is_server_controlled_and_approval_is_explicit(app_setup):
    app, client, engine, qid = app_setup
    assert client.get("/v1/admin/questions").status_code == 401
    unprivileged = create_app(engine, Settings(database_url="", local_development=True, local_token=TOKEN))
    with TestClient(unprivileged) as ordinary:
        assert ordinary.get("/v1/admin/questions", headers=AUTH).status_code == 403
        assert not ordinary.get("/v1/me/account", headers=AUTH).json()["content_reviewer"]
    old = client.get("/v1/admin/questions/" + qid, headers=AUTH).json()
    response = client.post("/v1/admin/questions/" + qid, headers=AUTH,
                           json={"action": "approve", "expected_checksum": old["checksum"]})
    assert response.status_code == 422
    result = publish_question(client, qid)
    assert result["document"]["review"]["reviewer"] == "local-developer"
    assert result["id"].endswith("@2")
    with transaction(engine) as db:
        assert db.get(Question, qid).status == "draft"
        assert db.scalar(select(func.count()).select_from(ReviewEvent)) == 1


def test_question_edits_withdrawal_and_stale_reviews_fail_closed(app_setup):
    _, client, engine, qid = app_setup
    published = publish_question(client, qid)
    route = "/v1/admin/questions/" + published["id"]
    started = client.post("/v1/sessions", headers=AUTH, json={}).json()
    assert client.get("/v1/sessions/" + started["session_id"], headers=AUTH).json()["question"]
    response = client.post(route, headers=AUTH, json={"action": "withdraw", "expected_checksum": published["checksum"], "note": "Synthetic content withdrawn in a test."})
    assert response.status_code == 200
    assert client.get("/v1/sessions/" + started["session_id"], headers=AUTH).status_code == 409
    with transaction(engine) as db:
        assert available_questions(db, "divisibility", "practice") == []
    assert client.post(route, headers=AUTH, json={"action": "approve", "expected_checksum": published["checksum"], "confirm_reviewed": True}).status_code == 409


def test_runtime_publications_and_private_drafts(app_setup):
    app, client, engine, _ = app_setup
    assert client.get("/v1/curriculum", headers=AUTH).json()["skills"][0]["lesson"] is None
    publish_document(client, "curriculum")
    assert client.get("/v1/curriculum", headers=AUTH).json()["skills"][0]["lesson"]
    assert app.state.personalisation.teaching("local-developer", "divisibility")["content_available"]
    published = publish_document(client, "notes:divisibility", {"text": "Reviewed synthetic note A."})
    assert topic_notes(engine, "divisibility") == "Reviewed synthetic note A."
    route = "/v1/admin/documents/notes:divisibility"
    edited = client.post(route, headers=AUTH, json={"action": "save", "expected_checksum": published["checksum"], "document": {"text": "Draft B."}}).json()
    assert topic_notes(engine, "divisibility") == "Reviewed synthetic note A."
    assert client.post(route, headers=AUTH, json={"action": "approve", "expected_checksum": edited["checksum"], "document": {"text": "Unreviewed replacement"}, "confirm_reviewed": True}).status_code == 422
    assert client.post(route, headers=AUTH, json={"action": "withdraw", "expected_checksum": edited["checksum"]}).status_code == 200
    assert topic_notes(engine, "divisibility") == ""


def test_exam_profile_publication_and_goal_use(app_setup):
    _, client, _, _ = app_setup
    document = {"schema_version": 1, "status": "draft", "profiles": [{
        "id": "test-profile", "name": "Synthetic profile", "target_skill_ids": ["divisibility"], "default_mastery_bar": 0.75}]}
    publish_document(client, "exam-profiles", document)
    assert client.get("/v1/curriculum", headers=AUTH).json()["exam_profiles"][0]["id"] == "test-profile"
    result = client.put("/v1/me/goal", headers=AUTH, json={"exam_profile_id": "test-profile"})
    assert result.status_code == 200 and "divisibility" in result.json()["route_skill_ids"]


def test_report_requires_an_owned_exposed_question_and_reviewer_resolution(app_setup):
    _, client, _, qid = app_setup
    publish_question(client, qid)
    assert client.post("/v1/assignments/not-mine/report", headers=AUTH, json={"message": "Synthetic test report."}).status_code == 404
    sid = client.post("/v1/sessions", headers=AUTH, json={}).json()["session_id"]
    item = client.get("/v1/sessions/" + sid, headers=AUTH).json()["question"]
    result = client.post("/v1/assignments/" + item["assignment_id"] + "/report", headers=AUTH, json={"message": "Synthetic report: inspect this wording."})
    assert result.status_code == 201
    reports = client.get("/v1/admin/reports", headers=AUTH).json()
    assert reports[0]["id"] == result.json()["id"]
    assert client.post("/v1/admin/reports/" + result.json()["id"] + "/resolve", headers=AUTH, json={"resolution": "Synthetic test resolution recorded."}).status_code == 200


def test_export_is_owned_and_delete_revokes_identity(app_setup):
    app, client, engine, qid = app_setup
    publish_question(client, qid)
    service = app.state.service
    service.register("another-learner")
    other = service.create_session("another-learner")
    service.abandon("another-learner", other["session_id"])
    sid = client.post("/v1/sessions", headers=AUTH, json={}).json()["session_id"]
    assert client.get("/v1/me/export", headers=AUTH).status_code == 409
    item = client.get("/v1/sessions/" + sid, headers=AUTH).json()["question"]
    client.post("/v1/assignments/" + item["assignment_id"] + "/submit", headers={**AUTH, "Idempotency-Key": "private-export"}, json={"answer": "999", "working": "my private working"})
    exported = client.get("/v1/me/export", headers=AUTH)
    assert exported.status_code == 200
    data = exported.json()["data"]
    assert data["attempts"][0]["working"] == "my private working"
    assert len(data["learning_sessions"]) == 1 and "question_versions" not in data
    assert client.delete("/v1/me/account", headers=AUTH).status_code == 422
    result = client.request("DELETE", "/v1/me/account", headers=AUTH, json={"confirmation": "DELETE"})
    assert result.status_code == 200 and result.json()["data_deleted"]
    assert client.get("/v1/me/account", headers=AUTH).status_code == 403
    with transaction(engine) as db:
        assert not db.get(Learner, "local-developer") and db.get(Learner, "another-learner")
        assert db.get(DeletedIdentity, "local-developer")


def test_identity_delete_failure_is_retryable_without_restoring_local_data(app_setup, monkeypatch):
    _, client, engine, _ = app_setup
    client.get("/v1/me/account", headers=AUTH)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "synthetic-test-only")
    settings = Settings(database_url="", supabase_url="https://example.supabase.co")
    calls = []
    def failed(*args):
        calls.append(1)
        raise RuntimeError("synthetic failure")
    service = AccountService(engine, settings, failed)
    result = service.delete("local-developer")
    assert result["data_deleted"] and not result["identity_deleted"] and calls
    service.delete_identity = lambda *args: None
    assert service.finish_identity_deletion("local-developer")["identity_deleted"]


def test_tutor_budget_is_atomic_and_cached_visits_do_not_consume_calls(app_setup, monkeypatch):
    _, client, engine, _ = app_setup
    monkeypatch.setenv("MASTRR_TUTOR_DAILY_CALLS", "2")
    budget = BudgetService(engine)
    with ThreadPoolExecutor(max_workers=4) as executor:
        accepted = list(executor.map(lambda _: budget.reserve("someone", 1000), range(8)))
    assert sum(accepted) == 2
    client.get("/v1/me/account", headers=AUTH)
    payload = {"choices": [{"message": {"content": "Synthetic lesson."}, "finish_reason": "stop"}], "usage": {}}
    tutor = TutorService(engine, TutorSettings(api_key="test"), completion=lambda *args: payload, notes=lambda _: "Synthetic note.")
    first = tutor.tutor("local-developer", "divisibility")
    second = tutor.tutor("local-developer", "divisibility")
    assert len(first["usage"]) == 1 and second["usage"] == []
    assert tutor.budget.status("local-developer")["calls"] == 1


def test_rate_limits_and_production_local_auth_guard(app_setup, monkeypatch):
    _, _, engine, _ = app_setup
    monkeypatch.setenv("MASTRR_API_REQUESTS_PER_MINUTE", "2")
    app = create_app(engine, Settings(database_url="", local_development=True, local_token=TOKEN))
    with TestClient(app) as client:
        assert client.get("/v1/me/account", headers=AUTH).status_code == 200
        assert client.get("/v1/me/account", headers=AUTH).status_code == 200
        result = client.get("/v1/me/account", headers=AUTH)
        assert result.status_code == 429 and result.headers["Retry-After"] == "60"
    monkeypatch.setenv("MASTRR_ENV", "production")
    with pytest.raises(ValueError, match="Production"):
        create_app(engine, Settings(database_url="", local_development=True, local_token=TOKEN))


def test_tutor_completion_requires_ownership_and_changes_no_grade(app_setup):
    app, client, engine, _ = app_setup
    publish_document(client, "notes:divisibility", {"text": "Synthetic reviewed note."})
    record = client.post("/v1/me/tutor/divisibility", headers=AUTH).json()
    wrong = client.post("/v1/me/tutor/divisibility/complete", headers=AUTH, json={"tutoring_id": "not-owned"})
    assert wrong.status_code == 404
    result = client.post("/v1/me/tutor/divisibility/complete", headers=AUTH, json={"tutoring_id": record["id"]})
    assert result.status_code == 200
    assert next(g for g in app.state.service.gaps("local-developer") if g["skill_id"] == "divisibility")["status"] == "unassessed"


def test_changed_assessment_content_withholds_current_claim_without_rewriting_history(app_setup):
    app, client, engine, qid = app_setup
    from backend.models import GapState
    published = publish_question(client, qid)
    sid = client.post("/v1/sessions", headers=AUTH, json={}).json()["session_id"]
    item = client.get("/v1/sessions/" + sid, headers=AUTH).json()["question"]
    client.post("/v1/assignments/" + item["assignment_id"] + "/submit", headers={**AUTH, "Idempotency-Key": "stale-assessment"}, json={"answer": "4"})
    with transaction(engine) as db:
        db.add(GapState(learner_id="local-developer", skill_id="divisibility", status="mastered", source_session_id=sid, updated_at="2026-10-27T00:00:00+00:00"))
    client.post("/v1/admin/questions/" + published["id"], headers=AUTH, json={"action": "withdraw", "expected_checksum": published["checksum"]})
    row = next(g for g in app.state.service.gaps("local-developer") if g["skill_id"] == "divisibility")
    assert row["evidence_stale"] and row["status"] == "unassessed" and row["previous_status"] == "mastered"
    with transaction(engine) as db:
        assert db.get(GapState, ("local-developer", "divisibility")).status == "mastered"


def test_private_export_never_releases_validation_correctness(app_setup):
    _, client, engine, _ = app_setup
    from tests.test_scoring_flow import full_bank
    with transaction(engine) as db:
        import_questions(db, full_bank())
    created = client.post("/v1/topics/divisibility/validation", headers=AUTH)
    assert created.status_code == 201
    sid = created.json()["session_id"]
    while True:
        view = client.get("/v1/sessions/" + sid, headers=AUTH).json()
        if view["status"] == "completed":
            break
        assignment = view["question"]["assignment_id"]
        result = client.post("/v1/assignments/" + assignment + "/submit", headers={**AUTH, "Idempotency-Key": assignment}, json={"answer": "3"})
        assert result.status_code == 200 and "correct" not in result.json()
    exported = client.get("/v1/me/export", headers=AUTH).json()["data"]["attempts"]
    assert exported and all(row["source"] == "validation" and "correct" not in row and "response" not in row for row in exported)
