"""Goal routing and recommendation tests using synthetic, test-only content."""
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.content import import_questions
from backend.api import GoalBody, create_app
from backend.auth import Settings
from backend.curriculum import CurriculumError, load_curriculum, prerequisite_closure, validate_curriculum
from backend.exam_profiles import approved_profiles, validate_exam_profiles
from backend.db import Base, make_engine, transaction
from backend.learning import LearningService
from backend.numbers.bank import load_questions
from backend.practice import (review_days_after_pass, select_adaptive_questions,
                              select_fixed_questions, target_difficulty, update_progress)
from backend.personalisation import PersonalisationError, PersonalisationService
from backend.recommender import Action, TopicState, next_actions
from backend.teaching import teaching_mode, teaching_plan
from backend.mastery import rating_for
from backend.models import MasteryEstimate


@pytest.fixture
def graph():
    return {
        "schema_version": 1,
        "id": "sample",
        "skills": [
            {"id": "base", "title": "Foundations", "prerequisites": []},
            {"id": "percent", "title": "Percentages", "prerequisites": ["base"]},
            {"id": "profit", "title": "Profit and Loss", "prerequisites": ["percent"]},
        ],
    }


def test_route_closure_and_curriculum_cycle_validation(graph):
    assert prerequisite_closure(["profit"], graph) == ("base", "percent", "profit")
    broken = copy.deepcopy(graph)
    broken["skills"][0]["prerequisites"] = ["profit"]
    assert any("cycle" in error for error in validate_curriculum(broken))
    with pytest.raises(CurriculumError):
        prerequisite_closure(["missing"], graph)


def test_current_curriculum_has_draft_full_and_half_worked_examples():
    catalog = load_curriculum()
    assert catalog["status"] == "draft"
    assert all(skill.get("worked_example") and skill.get("half_worked_example")
               for skill in catalog["skills"])
    assert validate_curriculum(catalog) == []


def test_teaching_bands_and_unpublished_content_gate():
    skill = {
        "id": "topic", "lesson": "Lesson text",
        "worked_example": {"prompt": "P", "steps": ["A"], "answer": "1"},
        "half_worked_example": {"prompt": "P2", "steps": ["B"], "learner_prompt": "Finish"},
    }
    assert teaching_mode(None) == "worked_examples"
    assert teaching_mode(0.499) == "worked_examples"
    assert teaching_mode(0.50) == "hinted_practice"
    assert teaching_mode(0.75) == "hinted_practice"
    assert teaching_mode(0.751) == "practice_first"
    assert teaching_plan(skill, None, "draft")["worked_example"] is None
    assert teaching_plan(skill, None, "approved")["half_worked_example"] is not None
    assert teaching_plan(skill, 0.6, "approved")["hints_available"] is True
    assert teaching_plan(skill, 0.9, "approved")["explanation_after_mistake"] is True


def test_exam_profile_validation_requires_known_topics_and_review(graph):
    draft = {"schema_version": 1, "status": "draft", "profiles": []}
    assert validate_exam_profiles(draft, graph) == []
    approved = {
        "schema_version": 1, "status": "approved", "profiles": [{
            "id": "placement", "name": "Placement aptitude",
            "target_skill_ids": ["profit"], "default_mastery_bar": 0.75,
            "topic_bars": {"base": 0.8},
            "review": {"reviewer": "reviewer-1", "date": "2026-10-26"},
        }],
    }
    assert validate_exam_profiles(approved, graph) == []
    assert approved_profiles(approved)[0]["id"] == "placement"
    broken = copy.deepcopy(approved)
    broken["profiles"][0]["topic_bars"]["missing"] = 1.2
    assert any("unknown topic bar" in error or "bar must" in error
               for error in validate_exam_profiles(broken, graph))
    broken["profiles"][0]["review"].pop("reviewer")
    assert any("reviewer and date" in error for error in validate_exam_profiles(broken, graph))
    broken = copy.deepcopy(approved)
    broken["profiles"][0]["review"]["date"] = "not-a-date"
    assert any("YYYY-MM-DD" in error for error in validate_exam_profiles(broken, graph))


def test_recommendation_priority_and_lesson_to_practice_transition(graph):
    resume = Action("resume", "percent", "unfinished_activity", "Resume.")
    review = Action("review", "base", "due_review", "Review.")
    actions = next_actions(
        curriculum=graph, goal_targets=["profit"],
        states={"percent": TopicState(status="gap", phase="practice")},
        unfinished=resume, due_review=review, ready_to_retest=["percent"],
    )
    assert [action.kind for action in actions] == ["resume", "review", "retest"]
    actions = next_actions(
        curriculum=graph, goal_targets=["profit"],
        states={"percent": TopicState(status="gap", phase="tutoring_complete")},
    )
    assert actions[0].kind == "practice"


def test_missing_evidence_is_offered_for_diagnosis_and_completed_route_recognized(graph):
    actions = next_actions(curriculum=graph, goal_targets=["profit"], states={})
    assert actions[0].kind == "diagnostic" and actions[0].skill_id == "base"
    complete = {
        sid: TopicState(status=status)
        for sid, status in (("base", "mastered"), ("percent", "resolved"), ("profit", "mastered"))
    }
    assert next_actions(curriculum=graph, goal_targets=["profit"], states=complete)[0].kind == "route_complete"


@pytest.fixture
def personalisation(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "personalisation.db"))
    Base.metadata.create_all(engine)
    clock = [datetime(2026, 10, 26, tzinfo=timezone.utc)]
    learning = LearningService(engine, clock=lambda: clock[0])
    learning.register("learner-1")
    service = PersonalisationService(engine, learning)
    yield service, learning, engine, clock
    engine.dispose()


def test_goal_and_route_report_unassessed_content_availability(personalisation):
    service, _, _, _ = personalisation
    goal = service.set_goal("learner-1", ["hcf-lcm"], "2026-12-01", "Asia/Kolkata")
    assert goal["route_skill_ids"] == [
        "integer-properties", "divisibility", "primes-factors", "hcf-lcm",
    ]
    roadmap = service.roadmap("learner-1")
    assert all(node["status"] == "unassessed" for node in roadmap["nodes"])
    assert all(node["available"] is False for node in roadmap["nodes"])
    assert roadmap["next_actions"] == []
    with pytest.raises(PersonalisationError, match="timezone"):
        service.set_goal("learner-1", ["hcf-lcm"], timezone="Not/A_Timezone")
    with pytest.raises(PersonalisationError, match="profile"):
        service.set_goal("learner-1", ["hcf-lcm"], exam_profile_id="bank-po")


def test_approved_exam_profile_is_snapshotted_and_combines_optional_targets(personalisation, monkeypatch):
    import backend.personalisation as personalisation_module

    service, _, _, _ = personalisation
    document = {
        "schema_version": 3,
        "status": "approved",
        "profiles": [{
            "id": "bank-po", "name": "Bank PO",
            "target_skill_ids": ["digits-cyclicity"],
            "default_mastery_bar": 0.75,
            "topic_bars": {"digits-cyclicity": 0.8},
            "review": {"reviewer": "reviewer-1", "date": "2026-10-26"},
        }],
    }
    monkeypatch.setattr(personalisation_module, "load_exam_profiles", lambda: document)
    saved = service.set_goal("learner-1", ["hcf-lcm"], exam_profile_id="bank-po")
    assert saved["exam_profile_version"] == "3"
    assert saved["exam_profile_name"] == "Bank PO"
    assert saved["route_skill_ids"] == [
        "integer-properties", "divisibility", "primes-factors", "hcf-lcm",
        "remainders", "digits-cyclicity",
    ]
    reread = service.get_goal("learner-1")
    assert reread["exam_profile_id"] == "bank-po"
    assert reread["route_skill_ids"] == saved["route_skill_ids"]
    roadmap = service.roadmap("learner-1")
    bars = {node["skill_id"]: node["mastery_bar"] for node in roadmap["nodes"]}
    assert bars["digits-cyclicity"] == 0.8
    assert bars["remainders"] == 0.75


def test_teaching_plan_changes_with_saved_learner_score(personalisation, monkeypatch):
    import backend.personalisation as personalisation_module

    service, _, engine, _ = personalisation
    catalog = {
        "schema_version": 1, "id": "test", "status": "approved",
        "review": {"reviewer": "reviewer-1", "date": "2026-10-26"},
        "skills": [{
            "id": "topic", "title": "Topic", "prerequisites": [], "objective": "Learn",
            "lesson": "Read this idea.",
            "worked_example": {"prompt": "Solve 2 + 2", "steps": ["Add"], "answer": "4"},
            "half_worked_example": {"prompt": "Solve 3 + 3", "steps": ["Start"], "learner_prompt": "Finish"},
        }],
    }
    monkeypatch.setattr(personalisation_module, "load_curriculum", lambda: catalog)
    assert service.teaching("learner-1", "topic")["mode"] == "worked_examples"
    with transaction(engine) as db:
        db.add(MasteryEstimate(learner_id="learner-1", skill_id="topic",
                               rating=rating_for(0.60), answer_count=2, recent_changes=[]))
    assert service.teaching("learner-1", "topic")["mode"] == "hinted_practice"
    with transaction(engine) as db:
        estimate = db.get(MasteryEstimate, ("learner-1", "topic"))
        estimate.rating = rating_for(0.9)
    assert service.teaching("learner-1", "topic")["explanation_after_mistake"] is True


def test_profile_api_lists_reviewed_profiles_and_accepts_profile_only_goal(tmp_path, monkeypatch):
    import backend.api as api_module
    import backend.personalisation as personalisation_module

    engine = make_engine("sqlite:///" + str(tmp_path / "profile-api.db"))
    Base.metadata.create_all(engine)
    app = create_app(engine, Settings(database_url="", local_development=True, local_token="t" * 32))
    app.state.service.register("learner-1")
    catalog = {
        "schema_version": 2, "status": "approved", "profiles": [{
            "id": "bank-po", "name": "Bank PO", "target_skill_ids": ["digits-cyclicity"],
            "default_mastery_bar": 0.75, "topic_bars": {"digits-cyclicity": 0.8},
            "review": {"reviewer": "reviewer-1", "date": "2026-10-26"},
        }],
    }
    monkeypatch.setattr(api_module, "load_exam_profiles", lambda: catalog)
    monkeypatch.setattr(personalisation_module, "load_exam_profiles", lambda: catalog)
    curriculum_route = next(route for route in app.routes if getattr(route, "path", None) == "/v1/curriculum")
    payload = curriculum_route.endpoint(owner="learner-1")
    assert payload["exam_profiles"][0]["id"] == "bank-po"
    goal_route = next(route for route in app.routes
                      if getattr(route, "path", None) == "/v1/me/goal" and "PUT" in route.methods)
    goal = goal_route.endpoint(body=GoalBody(exam_profile_id="bank-po"), owner="learner-1")
    assert goal["target_skill_ids"] == []
    assert goal["route_skill_ids"][-1] == "digits-cyclicity"
    engine.dispose()


def test_recommendation_display_log_rejects_stale_state_and_dismisses(personalisation):
    service, _, engine, _ = personalisation
    service.set_goal("learner-1", ["divisibility"])
    draft = next(q for q in load_questions() if q["skill_id"] == "divisibility"
                 and q["purpose"] == "diagnostic")
    with transaction(engine) as db:
        items = []
        for i in range(8):
            question = copy.deepcopy(draft)
            question.update(
                id=f"personalisation-fixture-{i}", family_id=f"fixture-family-{i}",
                difficulty_level=3 + i % 2, review_status="approved", hidden=False,
                review={"reviewer": "test-only-fixture", "date": "test-only"},
            )
            items.append(question)
        import_questions(db, items)
    preview = service.next_action("learner-1")
    assert preview["actions"][0]["kind"] == "diagnostic"
    logged = service.record_recommendation("learner-1", preview["state_fingerprint"])
    dismissed = service.dismiss_recommendation("learner-1", logged["recommendation_id"])
    assert dismissed["status"] == "dismissed"
    service.set_goal("learner-1", ["hcf-lcm"])
    with pytest.raises(PersonalisationError, match="changed"):
        service.record_recommendation("learner-1", preview["state_fingerprint"])


def test_adaptive_practice_targets_eighty_percent_and_caps_stuck_rule():
    assert target_difficulty(0.0) == 2
    assert target_difficulty(1.4) == 3
    assert target_difficulty(3.0) == 5
    state = None
    count, best, recent = 0, None, []
    for _ in range(9):
        state = update_progress(count=count, best_score=best, recent_scores=recent,
                                score=0.55, mastery_bar=0.75)
        count, best, recent = state.count, state.best_score, list(state.recent_scores)
    assert state.stuck is False
    state = update_progress(count=count, best_score=best, recent_scores=recent,
                            score=0.55, mastery_bar=0.75)
    assert state.count == 10
    assert state.stuck is True
    assert state.ready_for_retest is False
    assert [review_days_after_pass(i) for i in range(4)] == [3, 7, 21, None]


def test_practice_progress_only_unlocks_retest_after_minimum_answers():
    assert update_progress(count=3, best_score=0.7, recent_scores=[0.6, 0.7, 0.7],
                           score=0.76, mastery_bar=0.75).ready_for_retest is False
    assert update_progress(count=4, best_score=0.7, recent_scores=[0.6, 0.7, 0.7, 0.76],
                           score=0.76, mastery_bar=0.75).ready_for_retest is True


def test_practice_pickers_use_fresh_unique_families_and_distinct_policies():
    questions = [SimpleNamespace(
        id=f"q-{level}", family_id=f"f-{level}", difficulty_level=level, hidden=False,
    ) for level in range(1, 6)]
    assert select_adaptive_questions(questions, 1.4, 3)[0].difficulty_level == 3
    assert [q.difficulty_level for q in select_fixed_questions(questions, 5)] == [1, 2, 3, 4, 5]
    assert len(select_adaptive_questions(questions + [questions[2]], 1.4, 10)) == 5
