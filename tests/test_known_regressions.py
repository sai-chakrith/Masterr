"""Confirmed audit defects. Strict xfails preserve the intended behaviour until fixed.

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
from backend.learning import LearningService
from backend.models import Learner, LearnerGoal, Question
from backend.operations import AccountService, BudgetService
from backend.personalisation import PersonalisationService
from tests.test_mcq_feedback import mcq_fixture
from tests.test_scoring_flow import bank
from tests.test_timed_practice import timed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="QA-1: roadmap/teaching reveal live independent-test scores")
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="QA-2: independent MCQ tests disclose immediate teaching feedback")
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="QA-3: deletion can race the separate tombstone check and registration")
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="QA-4: mixed timed practice silently omits a requested topic")
def test_mixed_timed_test_requires_coverage_for_every_requested_topic(timed):
    service, _, engine, _ = timed
    with transaction(engine) as db:
        for q in db.scalars(select(Question).where(Question.skill_id == "integer-properties")):
            q.status = "withdrawn"
    run_id = service.start("alice", ["divisibility", "integer-properties"], 4, 5)["id"]
    with transaction(engine) as db:
        run = db.get(TimedTest, run_id)
        covered = {db.get(Question, qid).skill_id for qid in run.question_ids}
        assert covered == set(run.skill_ids)
