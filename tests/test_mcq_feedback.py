import copy
from datetime import datetime, timezone

from sqlalchemy import select

from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningService
from backend.models import Attempt, QuestionOption
from backend.numbers.bank import load_questions, validate_bank


def mcq_fixture():
    question = copy.deepcopy(next(q for q in load_questions() if q["id"] == "num-003"))
    question.update(id="mcq-divisibility-1", family_id="mcq-divisibility-family",
                    purpose="practice", review_status="approved",
                    difficulty_level=3, hidden=False,
                    review={"reviewer": "synthetic-test-fixture", "date": "test-only"},
                    provenance="SYNTHETIC_TEST_ONLY_NOT_HUMAN_APPROVED")
    question["options"] = [
        {"id": "a", "text": "The digit is 3", "value": 3},
        {"id": "b", "text": "The digit is 6", "value": 6, "misconception_id": "div-sum-multiple-3"},
        {"id": "c", "text": "The digit is 2", "value": 2, "misconception_id": "wrong-digit-sum"},
        {"id": "d", "text": "The digit is 9", "value": 9, "misconception_id": "wrong-digit-sum"},
    ]
    misconceptions = [
        {"id": "div-sum-multiple-3", "skill_id": "divisibility",
         "description": "You used a digit sum divisible by 3, but the question asks for divisibility by 9.",
         "short_fix": "Check whether the digit sum is a multiple of 9.", "review_status": "approved",
         "review": {"reviewer": "Synthetic fixture", "date": "2026-10-26"}},
        {"id": "wrong-digit-sum", "skill_id": "divisibility",
         "description": "This value does not make the digit sum a multiple of 9.",
         "short_fix": "Add the known digits first, then test the missing digit.", "review_status": "approved",
         "review": {"reviewer": "Synthetic fixture", "date": "2026-10-26"}},
    ]
    return question, misconceptions


def test_mcq_bank_requires_one_answer_and_tagged_wrong_options():
    question, misconceptions = mcq_fixture()
    assert validate_bank([question], misconceptions) == []
    question["options"][1].pop("misconception_id")
    assert any("needs a known misconception tag" in error
               for error in validate_bank([question], misconceptions))


def test_published_mcq_cannot_use_an_unreviewed_misconception():
    question, misconceptions = mcq_fixture()
    misconceptions[0]["review_status"] = "draft"
    misconceptions[0].pop("review")
    assert any("uses an unreviewed misconception" in error
               for error in validate_bank([question], misconceptions))


def test_mcq_session_hides_keys_and_returns_feedback_for_selected_misconception(tmp_path):
    question, misconceptions = mcq_fixture()
    second = copy.deepcopy(question)
    second.update(id="mcq-divisibility-2", family_id="mcq-divisibility-family-2")
    engine = make_engine("sqlite:///" + str(tmp_path / "mcq.db"))
    Base.metadata.create_all(engine)
    service = LearningService(engine, clock=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc))
    service.register("learner")
    with transaction(engine) as db:
        import_questions(db, [question, second], misconceptions)

    created = service.create_session("learner", "divisibility", "practice")
    current = service.get_session("learner", created["session_id"])
    assert current["question"]["options"] == [
        {"id": item["id"], "text": item["text"]} for item in question["options"]
    ]
    assert all("value" not in item and "misconception_id" not in item for item in current["question"]["options"])
    result = service.submit("learner", current["question"]["assignment_id"], "", "", "pick-b",
                            option_id="b")
    assert result["correct"] is False
    assert result["explanation"] == question["solution"]
    assert result["misconception_feedback"]["id"] == "div-sum-multiple-3"
    assert result["misconception_feedback"]["occurrence_count"] == 1
    assert result["misconception_feedback"]["targeted_reset"] is False
    next_question = service.get_session("learner", created["session_id"])["question"]
    repeated = service.submit("learner", next_question["assignment_id"], "", "", "pick-b-again",
                              option_id="b")
    assert repeated["misconception_feedback"]["occurrence_count"] == 2
    assert repeated["misconception_feedback"]["targeted_reset"] is True
    with transaction(engine) as db:
        attempts = list(db.scalars(select(Attempt)))
        options = list(db.scalars(select(QuestionOption)))
        assert attempts[0].selected_option_id == "b"
        assert attempts[0].misconception_id == "div-sum-multiple-3"
        assert attempts[0].normalized_answer == 6
        assert len(attempts) == 2
        assert len(options) == 8
    engine.dispose()
