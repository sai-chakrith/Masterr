"""K3/K4, S2, C3, C5 and the pilot forms against a full synthetic 35-question topic.

Approved fixtures here are synthetic test data, never publishable content.
"""
import copy
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend import mastery
from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningError, LearningService
from backend.models import Assignment, Attempt, MasteryEstimate, Question
from backend.numbers.bank import load_questions
from backend.numbers.coverage import HIDDEN_SPLIT, TARGET_SPLIT, audit, split_forms

RIGHT, WRONG = "3", "0"   # the seed question's answer is 3


def full_bank(skill="divisibility"):
    seed = next(q for q in load_questions() if q["id"] == "num-003")
    questions = []
    for level, count in TARGET_SPLIT.items():
        for i in range(count):
            q = copy.deepcopy(seed)
            q.update(id=f"bank-{level}-{i:02}", family_id=f"bank-{level}-{i:02}", skill_id=skill,
                     purpose="verification" if i % 2 else "diagnostic", difficulty_level=level,
                     hidden=i < HIDDEN_SPLIT[level], review_status="approved",
                     review={"reviewer": "synthetic-test-fixture", "date": "test-only"},
                     provenance="SYNTHETIC_TEST_ONLY_NOT_HUMAN_APPROVED")
            questions.append(q)
    forms = split_forms([q for q in questions if q["hidden"]])
    for q in questions:
        if q["hidden"]:
            q["validation_form"] = forms[q["id"]]
    return questions


@pytest.fixture
def bank(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "scoring.db"))
    Base.metadata.create_all(engine)
    clock = [datetime(2026, 11, 2, 9, tzinfo=timezone.utc)]
    service = LearningService(engine, clock=lambda: clock[0])
    for learner in ("ana", "ben"):
        service.register(learner)
    with transaction(engine) as db:
        import_questions(db, full_bank())
    yield service, engine, clock
    engine.dispose()


def run(service, learner, created, answers):
    """Answer in order; "" means I don't know. Returns the last response and the levels seen."""
    seen, response = [], None
    for i, answer in enumerate(answers):
        view = service.get_session(learner, created["session_id"])
        if view["question"] is None:
            break
        item = view["question"]
        response = service.submit(learner, item["assignment_id"], answer, "", f"{created['session_id']}-{i}",
                                  duration_ms=1000 + i, dont_know=answer == "")
        seen.append(item["question_version_id"])
    return response, seen


def levels_of(engine, ids):
    with transaction(engine) as db:
        return [db.get(Question, qid).difficulty_level for qid in ids]


def test_fixture_bank_meets_the_d7_split():
    report = audit(full_bank(), ["divisibility"])["divisibility"]
    assert report["problems"] == [] and report["total"] == 35


def test_new_diagnostic_alternates_near_the_bar_and_decides_mastered(bank):
    service, engine, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    created = service.create_session("ana", mode="diagnostic")
    assert created["policy_version"] == "mastery-diagnostic-v2" and created["question_count"] == 8
    response, seen = run(service, "ana", created, [RIGHT] * 12)
    assert levels_of(engine, seen) == [3, 4] * 4
    assert response["decision"] == "mastered" and response["answers"] == 8
    with transaction(engine) as db:
        estimate = db.get(MasteryEstimate, ("ana", "divisibility"))
        assert estimate.rating == pytest.approx(mastery.rescore([(lv, "right") for lv in [3, 4] * 4]))
        assert estimate.answer_count == 8
        attempts = list(db.scalars(select(Attempt)))
        assert {a.source for a in attempts} == {"diagnostic"}
        assert {a.scoring_version for a in attempts} == {"new"}
        assert all(a.predicted_probability is not None and a.duration_ms for a in attempts)
        assert not any(db.get(Question, a.question_id).hidden for a in db.scalars(select(Assignment)))
    assert next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")["status"] == "mastered"


def test_new_diagnostic_gap_and_one_diagnostic_per_topic(bank):
    service, _, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    created = service.create_session("ana", mode="diagnostic")
    response, _ = run(service, "ana", created, [WRONG] * 8)
    assert response["decision"] == "gap"
    with pytest.raises(LearningError) as error:
        service.create_session("ana", mode="diagnostic")
    assert error.value.code == "already_assessed"


def test_safety_zone_extends_one_question_at_a_time_without_repeats(bank):
    service, engine, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    created = service.create_session("ana", mode="diagnostic")
    pattern = [WRONG if i % 4 == 0 else RIGHT for i in range(12)]
    response, seen = run(service, "ana", created, pattern)
    assert response["decision"] == "borderline" and len(seen) == 12 == len(set(seen))
    assert levels_of(engine, seen) == [3, 4] * 6


def test_same_answers_in_any_order_give_the_same_decision(bank):
    service, _, _ = bank
    for learner, pattern in (("ana", [RIGHT] * 6 + [WRONG] * 2), ("ben", [WRONG] * 2 + [RIGHT] * 6)):
        service.set_scoring_version(learner, "divisibility", "new")
        created = service.create_session(learner, mode="diagnostic")
        run(service, learner, created, pattern + [RIGHT] * 4)
    # Both learners answered 3-and-4-level questions with the same counts; order differs.
    ana, ben = (next(g for g in service.gaps(x) if g["skill_id"] == "divisibility") for x in ("ana", "ben"))
    assert ana["status"] == ben["status"]


def test_help_is_closed_during_the_diagnostic(bank):
    service, _, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    created = service.create_session("ana", mode="diagnostic")
    item = service.get_session("ana", created["session_id"])["question"]
    with pytest.raises(LearningError, match="after the diagnostic"):
        service.help("ana", item["assignment_id"], "hint")


def test_retest_after_diagnostic_uses_only_unseen_questions(bank):
    service, engine, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    diagnostic = service.create_session("ana", mode="diagnostic")
    _, first = run(service, "ana", diagnostic, [WRONG] * 8)
    retest = service.create_session("ana", mode="verification", retest=True)
    assert retest["question_count"] == 10
    response, second = run(service, "ana", retest, [RIGHT] * 7 + [""] * 3)
    assert set(first).isdisjoint(second) and len(set(second)) == 10
    # 8 of the 16 visible level 3-4 questions were used, so 2 retest questions fall back.
    assert Counter(levels_of(engine, second)) == {3: 4, 4: 4, 2: 2}  # ties fall back to the easier level
    assert response["result"] == "retest_passed"
    with transaction(engine) as db:
        assert {a.source for a in db.scalars(select(Attempt)) if a.assignment_id in
                {x.id for x in service.assignments(db, retest["session_id"])}} == {"retest"}
        assert db.get(MasteryEstimate, ("ana", "divisibility")).answer_count == 18
    gap = next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")
    assert gap["status"] == "resolved" and gap["score"] < 0.99


def test_current_version_keeps_the_old_rules(bank):
    service, engine, _ = bank
    created = service.create_session("ana", mode="diagnostic")
    assert created["scoring_version"] == "current" and created["policy_version"] == "legacy-diagnostic-v0"
    item = service.get_session("ana", created["session_id"])["question"]
    with pytest.raises(LearningError, match="no I don't know"):
        service.submit("ana", item["assignment_id"], "", "", "skip", dont_know=True)
    response, seen = run(service, "ana", created, [RIGHT] * 3 + [WRONG] * 3)
    assert levels_of(engine, seen) == [1, 2, 3, 4, 5, 3]
    assert response["decision"] == "gap"  # 3 of 6 is not more than half
    retest = service.create_session("ana", mode="verification", retest=True)
    assert retest["policy_version"] == "legacy-retest-v0" and retest["question_count"] == 3
    response, seen = run(service, "ana", retest, [RIGHT, RIGHT, WRONG])
    assert response["result"] == "retest_passed"
    assert levels_of(engine, seen) == [1, 2, 2]  # the easiest unseen questions
    with transaction(engine) as db:
        assert db.get(MasteryEstimate, ("ana", "divisibility")) is None
        assert {a.scoring_version for a in db.scalars(select(Attempt))} == {"current"}
    gap = next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")
    assert gap["score"] is None and gap["answer_count"] == 0


def test_legacy_diagnostic_marks_more_than_half_as_mastered(bank):
    service, _, _ = bank
    created = service.create_session("ana", mode="diagnostic")
    response, _ = run(service, "ana", created, [RIGHT] * 4 + [WRONG] * 2)
    assert response["decision"] == "mastered"


def test_switch_flips_a_topic_and_sessions_keep_their_version(bank):
    service, _, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    created = service.create_session("ana", mode="diagnostic")
    service.set_scoring_version("ana", "divisibility", "current")
    assert service.get_session("ana", created["session_id"])["scoring_version"] == "new"
    service.abandon("ana", created["session_id"])
    assert service.create_session("ana", mode="diagnostic")["scoring_version"] == "current"
    assert next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")["scoring_version"] == "current"
    with pytest.raises(LearningError):
        service.set_scoring_version("ana", "divisibility", "experimental")


def test_dashboard_shows_score_with_answer_count_and_hides_it_mid_retest(bank):
    service, _, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    diagnostic = service.create_session("ana", mode="diagnostic")
    run(service, "ana", diagnostic, [WRONG] * 8)
    gap = next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")
    assert gap["answer_count"] == 8 and 0 < gap["score"] < 0.6 and gap["mastery_bar"] == 0.75
    retest = service.create_session("ana", mode="verification", retest=True)
    run(service, "ana", retest, [RIGHT])
    gap = next(g for g in service.gaps("ana") if g["skill_id"] == "divisibility")
    assert gap["score"] is None and gap["score_withheld"]


def test_validation_forms_pre_post_delayed(bank):
    service, engine, clock = bank
    service.set_scoring_version("ana", "divisibility", "new")
    pre = service.create_validation("ana", "divisibility")
    assert pre["stage"] == "pre" and pre["form"] == "A" and pre["question_count"] == 5
    item = service.get_session("ana", pre["session_id"])["question"]
    with pytest.raises(LearningError, match="no hints"):
        service.help("ana", item["assignment_id"], "solution")
    response, form_a = run(service, "ana", pre, [RIGHT, WRONG, RIGHT, "", RIGHT])
    assert "outcomes" not in response and "correct" not in response
    assert response["result"] == "validation_completed"
    assert all("correct" not in a for a in service.get_session("ana", pre["session_id"])["attempts"])
    with pytest.raises(LearningError) as error:
        service.create_validation("ana", "divisibility")
    assert error.value.code == "validation_order"
    diagnostic = service.create_session("ana", mode="diagnostic")
    run(service, "ana", diagnostic, [RIGHT] * 8)
    post = service.create_validation("ana", "divisibility")
    assert post["stage"] == "post" and post["form"] == "B"
    _, form_b = run(service, "ana", post, [RIGHT] * 5)
    assert set(form_a).isdisjoint(form_b)
    assert sorted(levels_of(engine, form_a)) == [1, 3, 3, 4, 4]
    assert sorted(levels_of(engine, form_b)) == [2, 2, 3, 4, 5]
    with pytest.raises(LearningError) as error:
        service.create_validation("ana", "divisibility")
    assert error.value.code == "validation_not_due"
    clock[0] += timedelta(days=8)
    delayed = service.create_validation("ana", "divisibility")
    _, again = run(service, "ana", delayed, [RIGHT] * 5)
    assert delayed["stage"] == "delayed" and again == form_a
    with pytest.raises(LearningError) as error:
        service.create_validation("ana", "divisibility")
    assert error.value.code == "validation_complete"
    with transaction(engine) as db:
        validation = [a for a in db.scalars(select(Attempt)) if a.source == "validation"]
        assert len(validation) == 15 and all(a.predicted_probability is not None for a in validation)
        assert db.get(MasteryEstimate, ("ana", "divisibility")).answer_count == 8  # forms never move it


def test_pre_test_must_come_before_topic_work(bank):
    service, _, _ = bank
    created = service.create_session("ana", mode="diagnostic")
    service.abandon("ana", created["session_id"])
    with pytest.raises(LearningError) as error:
        service.create_validation("ana", "divisibility")
    assert error.value.code == "validation_order"


def test_hidden_questions_never_reach_diagnostic_or_retest(bank):
    service, engine, _ = bank
    service.set_scoring_version("ana", "divisibility", "new")
    diagnostic = service.create_session("ana", mode="diagnostic")
    _, first = run(service, "ana", diagnostic, [WRONG if i % 4 == 0 else RIGHT for i in range(12)])
    retest = service.create_session("ana", mode="verification", retest=True)
    _, second = run(service, "ana", retest, [RIGHT] * 10)
    with transaction(engine) as db:
        assert not any(db.get(Question, q).hidden for q in first + second)
