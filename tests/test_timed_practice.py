import copy
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from backend.app_models import TestExposure as TimedExposure
from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningError, LearningService
from backend.models import MasteryEstimate, Question
from backend.numbers.bank import load_questions
from backend.timed_practice import TimedPracticeService


@pytest.fixture
def timed(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "timed.db"))
    Base.metadata.create_all(engine)
    learning = LearningService(engine)
    learning.register("alice"); learning.register("bob")
    with transaction(engine) as db:
        for skill in ("divisibility", "integer-properties"):
            for i in range(8):
                q = copy.deepcopy(load_questions()[3])
                q.update(id=f"timed-{skill}-{i}", family_id=f"timed-family-{skill}-{i}", skill_id=skill,
                    purpose="practice", difficulty_level=3, review_status="approved",
                    review={"reviewer": "synthetic-test-only", "date": "test-only"})
                import_questions(db, [q])
    clock = [datetime.now(timezone.utc)]
    service = TimedPracticeService(engine, learning, lambda: clock[0])
    yield service, learning, engine, clock
    engine.dispose()


def test_mixed_test_hides_keys_and_results_and_enforces_ownership(timed):
    service, learning, engine, _ = timed
    run_id = service.start("alice", ["divisibility", "integer-properties"], 4, 5)["id"]
    view = service.get("alice", run_id)
    assert set(view["question"]) == {"id", "prompt", "skill_id", "options"}
    assert "correct" not in view and "outcomes" not in view
    with pytest.raises(LearningError, match="not found"):
        service.get("bob", run_id)
    with pytest.raises(LearningError, match="current question"):
        service.answer("alice", run_id, "wrong-id", "4", None, False)
    qid = view["question"]["id"]
    following = service.answer("alice", run_id, qid, "4", None, False)
    assert "correct" not in following
    assert service.answer("alice", run_id, qid, "4", None, False)["answered"] == 1
    with pytest.raises(LearningError, match="already saved"):
        service.answer("alice", run_id, qid, "999", None, False)
    result = service.finish("alice", run_id)
    assert result["correct"] == 1 and result["question_count"] == 4
    assert len({x["skill_id"] for x in result["outcomes"]}) == 2
    with transaction(engine) as db:
        assert db.get(MasteryEstimate, ("alice", "divisibility")) is None
        assert len(list(db.scalars(select(TimedExposure).where(TimedExposure.learner_id == "alice")))) == 4


def test_deadline_is_server_enforced_and_regular_activity_is_blocked(timed):
    service, learning, engine, clock = timed
    run_id = service.start("alice", ["divisibility"], 3, 1)["id"]
    view = service.get("alice", run_id)
    with pytest.raises(LearningError, match="current"):
        learning.create_session("alice", "divisibility")
    clock[0] += timedelta(minutes=2)
    expired = service.answer("alice", run_id, view["question"]["id"], "4", None, False)
    assert expired["status"] == "completed" and expired["answered"] == 0 and expired["correct"] == 0


def test_completed_test_reserves_families_from_future_assessments(timed):
    service, learning, engine, _ = timed
    run_id = service.start("alice", ["divisibility"], 3, 1)["id"]
    service.finish("alice", run_id)
    with transaction(engine) as db:
        seen = learning.seen_families(db, "alice")
        assert len(seen) == 3
    second = service.start("alice", ["divisibility"], 3, 1)["id"]
    service.finish("alice", second)
    with transaction(engine) as db:
        assert len(learning.seen_families(db, "alice")) == 6


def test_withdrawn_items_cannot_be_answered_or_explained(timed):
    service, _, engine, _ = timed
    run_id = service.start("alice", ["divisibility"], 3, 1)["id"]
    qid = service.get("alice", run_id)["question"]["id"]
    with transaction(engine) as db:
        db.get(Question, qid).status = "withdrawn"
    with pytest.raises(LearningError, match="withdrawn"):
        service.get("alice", run_id)
    result = service.finish("alice", run_id)
    assert result["outcomes"][0]["solution"].startswith("Content changed")


def test_insufficient_content_does_not_reserve_families(timed):
    service, learning, engine, _ = timed
    with pytest.raises(LearningError, match="Not enough"):
        service.start("alice", ["divisibility"], 10, 1)
    with transaction(engine) as db:
        assert learning.seen_families(db, "alice") == set()


def test_tutor_uses_completed_timed_mistakes_but_not_active_test_content(timed):
    service, _, engine, _ = timed
    from backend.tutor import TutorService, TutorSettings, IDK_ANSWER
    tutor = TutorService(engine, TutorSettings(), notes=lambda _: "Synthetic reviewed notes.")
    run_id = service.start("alice", ["divisibility"], 3, 1)["id"]
    with pytest.raises(LearningError, match="Finish or abandon"):
        tutor.tutor("alice", "divisibility")
    view = service.get("alice", run_id)
    while view["status"] == "active":
        view = service.answer("alice", run_id, view["question"]["id"], "", None, True)
    explanation = tutor.tutor("alice", "divisibility")
    assert len(explanation["selected_question_ids"]) == 3
    assert explanation["personal"].count(IDK_ANSWER) == 3
