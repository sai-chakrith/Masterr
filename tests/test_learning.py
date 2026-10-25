"""Approved fixtures below are synthetic test data, never publishable content."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.content import FACETS, import_questions
from backend.db import Base, make_engine, transaction
from backend.learning import LearningError, LearningService, normalized_integer
from backend.models import Assignment, Attempt, Exposure, Question
from backend.numbers.bank import load_questions


def fixtures():
    seed = next(q for q in load_questions() if q["id"] == "num-003")
    questions = []
    for purpose, count in (("diagnostic", 1), ("practice", 1), ("verification", 1), ("review", 2)):
        for occasion in range(count):
            for facet in FACETS:
                q = copy.deepcopy(seed)
                q.update(id=f"fixture-{purpose}-{occasion}-{facet}",
                         family_id=f"fixture-{purpose}-{occasion}-{facet}",
                         purpose=purpose, facet=facet, review_status="approved",
                         review={"reviewer": "synthetic-test-fixture", "date": "2026-10-23"},
                         provenance="SYNTHETIC_TEST_ONLY_NOT_HUMAN_APPROVED")
                questions.append(q)
    return questions


@pytest.fixture
def setup(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "learning.db"))
    Base.metadata.create_all(engine)
    instant = [datetime(2026, 10, 23, 12, tzinfo=timezone.utc)]
    service = LearningService(engine, clock=lambda: instant[0])
    service.register("alice")
    service.register("bob")
    with transaction(engine) as db:
        import_questions(db, fixtures())
    yield service, instant, engine
    engine.dispose()


def form(service, owner="alice", mode="verification", answers=None, review_id=None):
    created = service.create_session(owner, mode=mode, review_id=review_id)
    responses = []
    for answer in answers or ["3", "3", "3"]:
        item = service.get_session(owner, created["session_id"])["question"]
        responses.append(service.submit(owner, item["assignment_id"], answer, "", item["assignment_id"]))
    return created, responses


def test_form_withholds_feedback_and_creates_reviews_after_pass(setup):
    service, _, _ = setup
    created, responses = form(service)
    assert "correct" not in responses[0] and "outcomes" not in responses[0]
    assert "result" not in responses[1]
    assert responses[-1]["result"] == "independent_check_passed"
    today = service.today("alice")
    assert len(today["reviews"]) == 2
    assert [r["occasion"] for r in today["reviews"]] == [2, 7]
    assert not any(r["is_due"] for r in today["reviews"])
    assert today["evidence"][0]["session_id"] == created["session_id"]


def test_restart_preserves_resume_and_evidence(setup):
    service, instant, engine = setup
    created = service.create_session("alice")
    before = service.get_session("alice", created["session_id"])
    engine.dispose()
    restarted = LearningService(engine, clock=lambda: instant[0])
    assert restarted.get_session("alice", created["session_id"]) == before
    assert restarted.today("alice")["active_session_id"] == created["session_id"]


def test_wrong_form_has_no_retention_schedule(setup):
    service, _, _ = setup
    _, responses = form(service, answers=["3", "4", "3"])
    assert responses[-1]["result"] == "practice_needed"
    assert service.today("alice")["reviews"] == []


def test_help_ends_assessment_and_cannot_produce_pass(setup):
    service, _, _ = setup
    created = service.create_session("alice", mode="verification")
    item = service.get_session("alice", created["session_id"])["question"]
    assert service.help("alice", item["assignment_id"], "hint")["assessment_ended"]
    result = service.submit("alice", item["assignment_id"], "3", "", "helped")
    assert result["result"] == "assisted_practice"
    assert result["assistance"] == "hinted"
    assert service.today("alice")["reviews"] == []
    assert service.get_session("alice", created["session_id"])["question"] is None


def test_solution_exposure_is_recorded_before_answer(setup):
    service, _, engine = setup
    created = service.create_session("alice")
    item = service.get_session("alice", created["session_id"])["question"]
    service.help("alice", item["assignment_id"], "solution")
    result = service.submit("alice", item["assignment_id"], "3", "", "shown")
    assert result["assistance"] == "solution_exposed"
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(Exposure).where(Exposure.kind == "solution")) == 1


def test_solutions_unavailable_mid_form(setup):
    service, _, _ = setup
    created = service.create_session("alice", mode="verification")
    item = service.get_session("alice", created["session_id"])["question"]
    service.submit("alice", item["assignment_id"], "3", "", "first")
    with pytest.raises(LearningError, match="Finish"):
        service.help("alice", item["assignment_id"], "solution")


def test_public_view_excludes_private_content(setup):
    service, _, _ = setup
    created = service.create_session("alice")
    item = service.get_session("alice", created["session_id"])["question"]
    assert set(item) == {"assignment_id", "question_version_id", "prompt", "difficulty", "position", "facet"}


def test_duplicate_submission_and_conflicting_reuse(setup):
    service, _, engine = setup
    created = service.create_session("alice")
    aid = service.get_session("alice", created["session_id"])["question"]["assignment_id"]
    first = service.submit("alice", aid, "3", "digits", "same-key")
    assert service.submit("alice", aid, "3", "digits", "same-key") == first
    with pytest.raises(LearningError) as error:
        service.submit("alice", aid, "4", "digits", "same-key")
    assert error.value.code == "idempotency_conflict"
    with pytest.raises(LearningError):
        service.submit("alice", aid, "3", "digits", "different-key")
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(Attempt)) == 1


def test_two_concurrent_submissions_are_idempotent(setup):
    service, _, engine = setup
    created = service.create_session("alice")
    aid = service.get_session("alice", created["session_id"])["question"]["assignment_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.submit("alice", aid, "3", "", "concurrent"), range(2)))
    assert results[0] == results[1]
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(Attempt)) == 1


def test_cross_user_resources_are_hidden(setup):
    service, _, _ = setup
    created = service.create_session("alice")
    aid = service.get_session("alice", created["session_id"])["question"]["assignment_id"]
    actions = [
        lambda: service.get_session("bob", created["session_id"]),
        lambda: service.submit("bob", aid, "3", "", "bad"),
        lambda: service.help("bob", aid, "solution"),
        lambda: service.abandon("bob", created["session_id"]),
    ]
    for action in actions:
        with pytest.raises(LearningError) as error:
            action()
        assert error.value.status == 404
    assert service.today("bob") == {"active_session_id": None, "reviews": [], "evidence": []}


def test_no_submission_before_prompt_issued(setup):
    service, _, engine = setup
    created = service.create_session("alice")
    with transaction(engine) as db:
        aid = db.scalar(select(Assignment.id).where(Assignment.session_id == created["session_id"]))
    with pytest.raises(LearningError):
        service.submit("alice", aid, "3", "", "unopened")


def test_exhausted_form_does_not_partially_reserve_or_recycle(setup):
    service, _, engine = setup
    form(service)
    with pytest.raises(LearningError) as error:
        service.create_session("alice", mode="verification")
    assert error.value.code == "insufficient_coverage"
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(Exposure).where(Exposure.kind == "reserved")) == 3


def test_family_freshness_crosses_purposes(setup):
    service, _, engine = setup
    with transaction(engine) as db:
        practice = db.scalar(select(Question).where(Question.purpose == "practice"))
        verification = db.scalar(select(Question).where(Question.purpose == "verification", Question.facet == "basic"))
        practice.family_id = verification.family_id
    created = service.create_session("alice")
    service.abandon("alice", created["session_id"])
    with pytest.raises(LearningError) as error:
        service.create_session("alice", mode="verification")
    assert error.value.code == "insufficient_coverage"


def test_delayed_reviews_require_actual_due_date_and_new_families(setup):
    service, instant, _ = setup
    form(service)
    reviews = service.today("alice")["reviews"]
    with pytest.raises(LearningError) as error:
        service.create_session("alice", mode="review", review_id=reviews[0]["id"])
    assert error.value.code == "review_not_due"
    instant[0] += timedelta(days=2)
    _, result = form(service, mode="review", review_id=reviews[0]["id"])
    assert result[-1]["result"] == "later_check_passed"
    instant[0] += timedelta(days=5)
    _, result = form(service, mode="review", review_id=reviews[1]["id"])
    assert result[-1]["result"] == "later_check_passed"
    assert [r["status"] for r in service.today("alice")["reviews"]] == ["passed", "passed"]
    assert len(service.today("alice")["reviews"]) == 2


def test_unreviewed_seed_is_imported_idempotently_but_unavailable(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "drafts.db"))
    Base.metadata.create_all(engine)
    with transaction(engine) as db:
        assert import_questions(db, load_questions()) == 12
        assert import_questions(db, load_questions()) == 0
    service = LearningService(engine)
    service.register("student")
    with pytest.raises(LearningError) as error:
        service.create_session("student")
    assert error.value.code == "insufficient_coverage"
    engine.dispose()


def test_question_version_cannot_be_overwritten(setup):
    _, _, engine = setup
    changed = fixtures()[0]
    changed["prompt"] += " Changed."
    with pytest.raises(ValueError, match="new version"):
        with transaction(engine) as db:
            import_questions(db, [changed])


@pytest.mark.parametrize("answer", ["3.0", "3/1", "1+2", "True", "", "٣", "9999999999999", "2147483648"])
def test_answer_parser_rejects_ambiguous_or_out_of_range_input(answer):
    with pytest.raises(LearningError):
        normalized_integer(answer)


@pytest.mark.parametrize("answer", ["3", " +3 ", "003"])
def test_integer_normalization(answer):
    assert normalized_integer(answer) == 3


def test_completed_session_exposes_own_attempt_evidence_only(setup):
    service, _, _ = setup
    created, _ = form(service)
    completed = service.get_session("alice", created["session_id"])
    assert len(completed["attempts"]) == 3
    assert all(a["correct"] and a["assistance"] == "independent" for a in completed["attempts"])
    assert all("solution" not in a and "validator" not in a for a in completed["attempts"])


def test_timing_is_saved_and_retry_does_not_duplicate(setup):
    service, _, engine = setup
    created = service.create_session("alice", mode="practice")
    item = service.get_session("alice", created["session_id"])["question"]
    args = ("alice", item["assignment_id"], "3", "", "timed-answer")
    result = service.submit(*args, duration_ms=1234)
    assert service.submit(*args, duration_ms=1234) == result
    with transaction(engine) as db:
        attempts = list(db.scalars(select(Attempt)))
        assert len(attempts) == 1
        assert attempts[0].duration_ms == 1234
        assert attempts[0].scoring_version == "current"
    with pytest.raises(LearningError, match="different content"):
        service.submit(*args, duration_ms=1235)
    with pytest.raises(LearningError, match="Duration"):
        service.submit(*args, duration_ms=-1)


def test_hidden_questions_are_excluded_from_normal_selection(setup):
    from backend.content import available_questions
    service, _, engine = setup
    with transaction(engine) as db:
        questions = available_questions(db, "divisibility", "practice")
        assert questions
        hidden_id = questions[0].id
        questions[0].hidden = True
    with transaction(engine) as db:
        assert hidden_id not in {q.id for q in available_questions(db, "divisibility", "practice")}


@pytest.fixture
def retest_setup(setup):
    service, instant, engine = setup
    seed = next(q for q in load_questions() if q["id"] == "num-003")
    questions = []
    for i in range(25):
        q = copy.deepcopy(seed)
        q.update(id=f"retest-{i:02}", family_id=f"retest-{i:02}", purpose="verification",
                 facet="basic", review_status="approved",
                 review={"reviewer": "test-only", "date": "test-only"})
        questions.append(q)
    with transaction(engine) as db:
        import_questions(db, questions)
        for q in db.scalars(select(Question).where(Question.item_id.like("retest-%"))):
            q.difficulty_level = 3 if int(q.item_id[-2:]) < 20 else 2
    return setup


@pytest.mark.parametrize("right,expected", [(6, "gap"), (7, "resolved"), (10, "resolved"), (0, "gap")])
def test_retest_boundary_skip_and_persistent_gap(retest_setup, right, expected):
    from backend.models import MasteryEstimate
    service, _, engine = retest_setup
    created = service.create_session("alice", mode="verification", retest=True)
    assert created["question_count"] == 10
    for i in range(10):
        item = service.get_session("alice", created["session_id"])["question"]
        result = service.submit("alice", item["assignment_id"], "3" if i < right else "", "",
                                item["assignment_id"], dont_know=i >= right)
        if i < 9:
            assert "correct" not in result and "outcomes" not in result
    assert result["result"] == ("retest_passed" if right >= 7 else "retest_practice_needed")
    for _ in range(2):
        gap = next(g for g in service.gaps("alice") if g["skill_id"] == "divisibility")
        assert gap["status"] == expected
    assert all(g["status"] == "unassessed" for g in service.gaps("bob"))
    with transaction(engine) as db:
        assert db.get(MasteryEstimate, ("alice", "divisibility")) is None


def test_retest_freshness_and_atomic_exhaustion(retest_setup):
    service, _, engine = retest_setup
    first = service.create_session("alice", mode="verification", retest=True)
    service.abandon("alice", first["session_id"])
    second = service.create_session("alice", mode="verification", retest=True)
    with transaction(engine) as db:
        a = {q.question_id for q in service.assignments(db, first["session_id"])}
        b = {q.question_id for q in service.assignments(db, second["session_id"])}
        assert len(a) == len(b) == 10 and a.isdisjoint(b)
    service.abandon("alice", second["session_id"])
    with pytest.raises(LearningError, match="ten fresh"):
        service.create_session("alice", mode="verification", retest=True)
    assert service.today("alice")["active_session_id"] is None


def test_retest_help_cannot_resolve_gap(retest_setup):
    service, _, _ = retest_setup
    created = service.create_session("alice", mode="verification", retest=True)
    item = service.get_session("alice", created["session_id"])["question"]
    assert service.help("alice", item["assignment_id"], "hint")["assessment_ended"]
    result = service.submit("alice", item["assignment_id"], "3", "", "helped")
    assert result["result"] == "assisted_practice"
    assert next(g for g in service.gaps("alice") if g["skill_id"] == "divisibility")["status"] == "unassessed"


def test_borderline_review_is_owned_and_reuses_only_missed_items(setup):
    from backend.models import LearningSession
    service, _, engine = setup
    created = service.create_session("alice", mode="diagnostic")
    item = service.get_session("alice", created["session_id"])["question"]
    service.submit("alice", item["assignment_id"], "", "", "skip", dont_know=True)
    with transaction(engine) as db:
        service.set_gap(db, db.get(LearningSession, created["session_id"]), "borderline")
    result = service.borderline_review("alice", created["session_id"])
    assert len(result["items"]) == 1 and result["items"][0]["solution"]
    assert result["next_action"] == "retest"
    with pytest.raises(LearningError) as error:
        service.borderline_review("bob", created["session_id"])
    assert error.value.status == 404


def test_resolved_gap_reopens_only_after_new_independent_check(retest_setup):
    from backend.models import LearningSession
    service, _, engine = retest_setup
    # A prior decision remains stable across reads and ordinary practice.
    diagnostic = service.create_session("alice", mode="diagnostic")
    item = service.get_session("alice", diagnostic["session_id"])["question"]
    service.submit("alice", item["assignment_id"], "3", "", "diag")
    with transaction(engine) as db:
        service.set_gap(db, db.get(LearningSession, diagnostic["session_id"]), "resolved")
    form(service, mode="practice", answers=["0"])
    assert next(g for g in service.gaps("alice") if g["skill_id"] == "divisibility")["status"] == "resolved"
    form(service, answers=["0", "0", "0"])
    assert next(g for g in service.gaps("alice") if g["skill_id"] == "divisibility")["status"] == "gap"


def test_retest_uses_fallback_only_after_middle_levels_and_ignores_hidden(retest_setup):
    service, _, engine = retest_setup
    with transaction(engine) as db:
        for q in db.scalars(select(Question).where(Question.item_id.like("retest-%"))):
            if int(q.item_id[-2:]) < 15:
                q.hidden = True
    created = service.create_session("alice", mode="verification", retest=True)
    with transaction(engine) as db:
        questions = [db.get(Question, a.question_id) for a in service.assignments(db, created["session_id"])]
        assert [q.difficulty_level for q in questions] == [3] * 5 + [2] * 5
        assert not any(q.hidden for q in questions)


def test_import_preserves_explicit_question_metadata(setup):
    _, _, engine = setup
    q = copy.deepcopy(fixtures()[0])
    q.update(id="metadata-fixture", family_id="metadata-fixture", difficulty_level=4,
             hidden=True, sub_topic="combined-rules")
    with transaction(engine) as db:
        import_questions(db, [q])
        saved = db.get(Question, "metadata-fixture@1")
        assert saved.difficulty_level == 4 and saved.hidden and saved.sub_topic == "combined-rules"
