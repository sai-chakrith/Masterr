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
