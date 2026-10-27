"""Regression checks for the repaired audit defects.

All content and identities below are synthetic, never real reviewer approvals.
"""
import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.api import create_app
from backend.app_models import DeletedIdentity, TimedTest
from backend.auth import Settings
from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningError, LearningService
from backend.models import Learner, LearnerGoal, Question
from backend.operations import AccountService, BudgetService
from backend.personalisation import PersonalisationService
from tests.test_mcq_feedback import mcq_fixture
from tests.test_scoring_flow import bank
from tests.test_timed_practice import timed


def test_independent_test_withholds_score_across_all_endpoints(bank):
    learning, engine, _ = bank
    learning.set_scoring_version("ana", "divisibility", "new")
    personal = PersonalisationService(engine, learning)
    personal.set_goal("ana", ["divisibility"])
    run = learning.create_session("ana", "divisibility", "verification", retest=True)
    question = learning.get_session("ana", run["session_id"])["question"]
    reply = learning.submit("ana", question["assignment_id"], "3", "", "qa-score")
    assert not reply["session_complete"] and "correct" not in reply
    assert next(g for g in learning.gaps("ana") if g["skill_id"] == "divisibility")["score"] is None
    roadmap_score = next(n for n in personal.roadmap("ana")["nodes"] if n["skill_id"] == "divisibility")["score"]
    teaching_score = personal.teaching("ana", "divisibility")["score"]
    assert (roadmap_score, teaching_score) == (None, None)


def test_independent_mcq_test_does_not_teach_between_questions(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "mcq.db"))
    Base.metadata.create_all(engine)
    try:
        learning = LearningService(engine)
        learning.register("synthetic-learner")
        learning.set_scoring_version("synthetic-learner", "divisibility", "new")
        seed, concepts = mcq_fixture()
        questions = []
        for i in range(10):
            q = copy.deepcopy(seed)
            q.update(id=f"qa-mcq-{i}", family_id=f"qa-mcq-family-{i}", purpose="verification")
            questions.append(q)
        with transaction(engine) as db:
            import_questions(db, questions, concepts)
        run = learning.create_session("synthetic-learner", "divisibility", "verification", retest=True)
        question = learning.get_session("synthetic-learner", run["session_id"])["question"]
        reply = learning.submit("synthetic-learner", question["assignment_id"], "", "", "qa-mcq", option_id="b")
        assert not reply["session_complete"] and "correct" not in reply
        assert "misconception_feedback" not in reply
    finally:
        engine.dispose()


def test_inflight_request_cannot_recreate_data_after_account_deletion(tmp_path, monkeypatch):
    engine = make_engine("sqlite:///" + str(tmp_path / "deletion.db"))
    Base.metadata.create_all(engine)
    token = "synthetic-local-token-" + "a" * 32
    settings = Settings(database_url="", local_development=True, local_token=token)
    app = create_app(engine, settings)
    LearningService(engine).register("local-developer")
    # Deterministically pause the request after its tombstone check, then finish
    # the other request's deletion before this request resumes registration.
    def intervening_deletion(self, owner):
        AccountService(engine, settings).delete(owner)
    monkeypatch.setattr(BudgetService, "rate_limit", intervening_deletion)
    try:
        with TestClient(app) as client:
            response = client.put("/v1/me/goal", headers={"Authorization": "Bearer " + token},
                                  json={"target_skill_ids": ["divisibility"]})
        with transaction(engine) as db:
            assert db.get(DeletedIdentity, "local-developer") is not None
            recreated = db.get(Learner, "local-developer") is not None
            saved_goal = db.get(LearnerGoal, "local-developer") is not None
        assert (response.status_code, recreated, saved_goal) == (403, False, False)
    finally:
        engine.dispose()


def test_mixed_timed_test_requires_coverage_for_every_requested_topic(timed):
    service, _, engine, _ = timed
    with transaction(engine) as db:
        for q in db.scalars(select(Question).where(Question.skill_id == "integer-properties")):
            q.status = "withdrawn"
    with pytest.raises(LearningError, match="Every selected topic"):
        service.start("alice", ["divisibility", "integer-properties"], 4, 5)
    with transaction(engine) as db:
        assert db.scalar(select(TimedTest)) is None


def test_completed_retest_keeps_result_after_reload(bank):
    service, _, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    run = service.create_session("ana", "divisibility", "verification", retest=True)
    while True:
        question = service.get_session("ana", run["session_id"])["question"]
        reply = service.submit("ana", question["assignment_id"], "3", "", question["assignment_id"])
        if reply["session_complete"]:
            break
    reopened = service.get_session("ana", run["session_id"])
    assert reopened["completion"]["result"] == reply["result"]
    assert reopened["completion"]["outcomes"] == reply["outcomes"]
    assert len(reopened["completion"]["outcomes"]) == 10


def test_adaptive_practice_varies_methods_within_target_level():
    from types import SimpleNamespace
    from backend.practice import select_adaptive_questions
    questions = [SimpleNamespace(id=str(i), family_id=str(i), hidden=False,
                 difficulty_level=1, sub_topic=str(i//4)) for i in range(12)]
    chosen = select_adaptive_questions(questions, -2, 3)
    assert len({q.sub_topic for q in chosen}) == 3
