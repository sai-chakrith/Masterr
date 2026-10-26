"""Storage and API-facing state assembly for goal-based learner journeys."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, func

from backend.curriculum import load_curriculum, prerequisite_closure
from backend.exam_profiles import approved_profiles, load_exam_profiles
from backend.learning import mastery_bar
from backend.db import transaction
from backend.mastery import shown_score
from backend.models import (
    Exposure,
    GapState,
    Learner,
    LearnerGoal,
    LearningProgress,
    LearningSession,
    MasteryEstimate,
    Question,
    RecommendationEvent,
    Review,
    TopicScoringConfig,
)
from backend.recommender import Action, TopicState, next_actions
from backend.teaching import teaching_plan


class PersonalisationError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class PersonalisationService:
    def __init__(self, engine, learning_service):
        self.engine = engine
        self.learning = learning_service

    def set_goal(self, learner, target_skill_ids, exam_date=None, timezone="Asia/Kolkata",
                 exam_profile_id=None):
        curriculum = load_curriculum()
        profile_document = load_exam_profiles()
        profile = next((item for item in approved_profiles(profile_document)
                        if item["id"] == exam_profile_id), None) if exam_profile_id else None
        if exam_profile_id and profile is None:
            raise PersonalisationError("profile_unavailable", "That exam profile is not reviewed and published.")
        target_skill_ids = list(dict.fromkeys(target_skill_ids or []))
        profile_targets = profile["target_skill_ids"] if profile else []
        route_targets = list(dict.fromkeys([*profile_targets, *target_skill_ids]))
        try:
            route = prerequisite_closure(route_targets, curriculum)
        except ValueError as exc:
            raise PersonalisationError("invalid_goal", str(exc)) from exc
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise PersonalisationError("invalid_timezone", "Choose a valid timezone.") from exc
        if exam_date:
            try:
                if date.fromisoformat(exam_date).isoformat() != exam_date:
                    raise ValueError
            except ValueError as exc:
                raise PersonalisationError("invalid_exam_date", "Use a valid YYYY-MM-DD date.") from exc
        now = self.learning.now()
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, learner)
            goal = db.get(LearnerGoal, learner)
            if goal is None:
                goal = LearnerGoal(learner_id=learner)
                db.add(goal)
            goal.curriculum_id = curriculum["id"]
            goal.curriculum_version = str(curriculum.get("schema_version", "1"))
            goal.target_skill_ids = target_skill_ids
            goal.exam_profile_id = exam_profile_id
            goal.exam_profile_version = str(profile_document["schema_version"]) if profile else None
            goal.exam_profile_snapshot = ({
                "id": profile["id"], "name": profile["name"],
                "target_skill_ids": profile_targets,
                "default_mastery_bar": profile.get("default_mastery_bar", 0.75),
                "topic_bars": profile.get("topic_bars", {}),
                "version": str(profile_document["schema_version"]),
            } if profile else None)
            goal.exam_date = exam_date
            goal.timezone = timezone
            goal.updated_at = now
        return {
            "curriculum_id": curriculum["id"],
            "curriculum_version": str(curriculum.get("schema_version", "1")),
            "target_skill_ids": list(dict.fromkeys(target_skill_ids)),
            "exam_profile_id": exam_profile_id,
            "exam_profile_version": str(profile_document["schema_version"]) if profile else None,
            "exam_profile_name": profile["name"] if profile else None,
            "route_skill_ids": list(route),
            "exam_date": exam_date,
            "timezone": timezone,
            "updated_at": now,
        }

    def get_goal(self, learner):
        with transaction(self.engine) as db:
            goal = db.get(LearnerGoal, learner)
            if goal is None:
                return None
            curriculum = load_curriculum()
            profile = goal.exam_profile_snapshot or {}
            route_targets = list(dict.fromkeys([
                *profile.get("target_skill_ids", []), *goal.target_skill_ids,
            ]))
            route = prerequisite_closure(route_targets, curriculum)
            return {
                "curriculum_id": goal.curriculum_id,
                "curriculum_version": goal.curriculum_version,
                "target_skill_ids": goal.target_skill_ids,
                "exam_profile_id": goal.exam_profile_id,
                "exam_profile_version": goal.exam_profile_version,
                "exam_profile_name": profile.get("name"),
                "route_skill_ids": list(route),
                "exam_date": goal.exam_date,
                "timezone": goal.timezone,
                "updated_at": goal.updated_at,
            }

    @staticmethod
    def fingerprint(payload):
        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

    @staticmethod
    def _availability(db, learner, skill_id, status):
        if status == "gap" and load_curriculum().get("status") != "approved":
            return False
        if status == "borderline":
            source = db.get(GapState, (learner, skill_id))
            session = db.get(LearningSession, source.source_session_id) if source and source.source_session_id else None
            return bool(session and session.status == "completed")
        else:
            purposes = ("diagnostic", "verification") if status == "unassessed" else ("practice",)
        seen = set(db.scalars(select(Exposure.family_id).where(Exposure.learner_id == learner)))
        candidates = list(db.scalars(select(Question).where(
            Question.skill_id == skill_id,
            Question.purpose.in_(purposes),
            Question.status == "approved",
            Question.hidden.is_(False),
        )))
        fresh = {q.family_id for q in candidates
                 if q.family_id not in seen and q.difficulty_level is not None}
        needed = 8 if status == "unassessed" else 1
        return len(fresh) >= needed

    @staticmethod
    def _retest_available(db, learner, skill_id):
        seen = set(db.scalars(select(Exposure.family_id).where(Exposure.learner_id == learner)))
        candidates = db.scalars(select(Question).where(
            Question.skill_id == skill_id,
            Question.purpose.in_(("diagnostic", "verification")),
            Question.status == "approved",
            Question.hidden.is_(False),
            Question.difficulty_level.is_not(None),
        ))
        return len({q.family_id for q in candidates if q.family_id not in seen}) >= 10

    def _snapshot(self, db, learner):
        curriculum = load_curriculum()
        goal = db.get(LearnerGoal, learner)
        if goal is None:
            raise PersonalisationError("goal_required", "Set a target to build your learning route.", 409)
        index = {skill["id"]: skill for skill in curriculum["skills"]}
        profile = goal.exam_profile_snapshot or {}
        route_targets = list(dict.fromkeys([
            *profile.get("target_skill_ids", []), *goal.target_skill_ids,
        ]))
        route = prerequisite_closure(route_targets, curriculum)
        gaps = {r.skill_id: r for r in db.scalars(
            select(GapState).where(GapState.learner_id == learner))}
        progress = {r.skill_id: r for r in db.scalars(
            select(LearningProgress).where(LearningProgress.learner_id == learner))}
        estimates = {r.skill_id: r for r in db.scalars(
            select(MasteryEstimate).where(MasteryEstimate.learner_id == learner))}
        configs = {r.skill_id: r.scoring_version for r in db.scalars(
            select(TopicScoringConfig).where(TopicScoringConfig.learner_id == learner))}
        states = {}
        for skill_id in route:
            assessment = gaps.get(skill_id)
            state = progress.get(skill_id)
            estimate = estimates.get(skill_id)
            score = shown_score(estimate.rating) if estimate and estimate.answer_count else None
            status = assessment.status if assessment else "unassessed"
            states[skill_id] = TopicState(
                status=status,
                phase=state.phase if state else ("tutoring" if status == "gap" else "none"),
                score=score,
                available=self._availability(db, learner, skill_id, status),
            )
        active = self.learning.active_session(db, learner)
        if active:
            title = index.get(active.skill_id, {}).get("title", active.skill_id)
            unfinished = Action("resume", active.skill_id, "unfinished_activity",
                                f"Resume your {active.mode} in {title}.")
        else:
            unfinished = None
        due = db.scalar(select(Review).where(
            Review.learner_id == learner,
            Review.status == "pending",
            Review.due_at <= self.learning.now(),
        ).order_by(Review.due_at))
        due_action = None
        if due:
            title = index.get(due.skill_id, {}).get("title", due.skill_id)
            due_action = Action("review", due.skill_id, "due_review",
                                f"A quick review of {title} is ready.")
        ready = tuple(skill_id for skill_id in route
                      if progress.get(skill_id) and progress[skill_id].phase == "ready_for_retest"
                      and self._retest_available(db, learner, skill_id))
        stuck = tuple(skill_id for skill_id in route
                      if progress.get(skill_id) and progress[skill_id].stuck and states[skill_id].available)
        actions = next_actions(
            curriculum=curriculum,
            goal_targets=route_targets,
            states=states,
            unfinished=unfinished,
            due_review=due_action,
            ready_to_retest=ready,
            stuck=stuck,
        )
        fingerprint = self.fingerprint({
            "targets": route_targets,
            "exam_profile_id": goal.exam_profile_id,
            "exam_profile_version": goal.exam_profile_version,
            "states": {sid: (state.status, state.phase, state.score, state.available)
                       for sid, state in states.items()},
            "active": active.id if active else None,
            "due_review": due.id if due else None,
        })
        return curriculum, goal, route, states, actions, fingerprint

    def next_action(self, learner):
        with transaction(self.engine) as db:
            curriculum, goal, route, states, actions, fingerprint = self._snapshot(db, learner)
            result = {
                "policy_version": "next-action-v1",
                "curriculum_version": str(curriculum.get("schema_version", "1")),
                "state_fingerprint": fingerprint,
                "availability": "ready" if actions else "no_reviewed_content_for_next_step",
                "actions": [action.__dict__ for action in actions],
            }
        return result

    def roadmap(self, learner):
        with transaction(self.engine) as db:
            curriculum, goal, route, states, actions, fingerprint = self._snapshot(db, learner)
            due_reviews = list(db.scalars(select(Review).where(
                Review.learner_id == learner,
                Review.status == "pending",
            ).order_by(Review.due_at)))
            index = {skill["id"]: skill for skill in curriculum["skills"]}
            nodes = []
            for skill_id in route:
                state = states[skill_id]
                estimate = db.get(MasteryEstimate, (learner, skill_id))
                nodes.append({
                    "skill_id": skill_id,
                    "title": index[skill_id]["title"],
                    "prerequisites": index[skill_id]["prerequisites"],
                    "status": state.status,
                    "phase": state.phase,
                    "score": state.score,
                    "mastery_bar": mastery_bar(skill_id, goal.exam_profile_snapshot),
                    "answer_count": estimate.answer_count if estimate else 0,
                    "next_review_at": next((item.due_at for item in due_reviews
                                            if item.skill_id == skill_id), None),
                    "source_session_id": (db.get(GapState, (learner, skill_id)).source_session_id
                                          if db.get(GapState, (learner, skill_id)) else None),
                    "available": state.available,
                })
            pace = None
            if goal.exam_date:
                today = datetime.fromisoformat(self.learning.now()).astimezone(
                    ZoneInfo(goal.timezone)).date()
                exam_day = date.fromisoformat(goal.exam_date)
                remaining = sum(states[sid].status not in {"mastered", "resolved"} for sid in route)
                days_left = (exam_day - today).days
                weeks_left = max(1, (days_left + 6) // 7) if days_left >= 0 else 0
                pace = {
                    "remaining_topics": remaining,
                    "weeks_left": weeks_left,
                    "topics_per_week": ((remaining + weeks_left - 1) // weeks_left) if weeks_left else None,
                    "exam_date_passed": days_left < 0,
                }
            return {
                "curriculum_id": goal.curriculum_id,
                "curriculum_version": goal.curriculum_version,
                "route_skill_ids": list(route),
                "nodes": nodes,
                "weekly_pace": pace,
                "next_actions": [action.__dict__ for action in actions],
                "state_fingerprint": fingerprint,
            }

    def teaching(self, learner, skill_id):
        curriculum = load_curriculum()
        skill = next((item for item in curriculum["skills"] if item["id"] == skill_id), None)
        if skill is None:
            raise PersonalisationError("unknown_skill", "Choose a skill in the current curriculum.", 404)
        with transaction(self.engine) as db:
            self.learning.lock_learner(db, learner)
            estimate = db.get(MasteryEstimate, (learner, skill_id))
            score = shown_score(estimate.rating) if estimate and estimate.answer_count else None
            return {
                "skill_id": skill_id,
                "curriculum_version": str(curriculum.get("schema_version", "1")),
                **teaching_plan(skill, score, curriculum.get("status", "draft")),
            }

    def record_recommendation(self, learner, state_fingerprint, action_index=0):
        if type(action_index) is not int or not 0 <= action_index <= 2:
            raise PersonalisationError("invalid_action", "Choose a displayed action.", 422)
        now = self.learning.now()
        with transaction(self.engine) as db:
            curriculum, _, _, _, actions, fingerprint = self._snapshot(db, learner)
            if fingerprint != state_fingerprint:
                raise PersonalisationError("stale_recommendation", "Your route changed. Refresh the suggestions.", 409)
            if action_index >= len(actions):
                raise PersonalisationError("invalid_action", "That action is not available.", 422)
            choice = actions[action_index]
            record = RecommendationEvent(
                id=str(uuid4()), learner_id=learner,
                action_kind=choice.kind, skill_id=choice.skill_id,
                reason_code=choice.reason_code, reason=choice.reason,
                alternatives=[action.__dict__ for action in actions[1:3]],
                state_fingerprint=fingerprint, policy_version="next-action-v1",
                status="shown", shown_at=now,
            )
            db.add(record)
            db.flush()
            return {"recommendation_id": record.id, "action": choice.__dict__,
                    "alternatives": [action.__dict__ for action in actions[1:3]]}

    def dismiss_recommendation(self, learner, recommendation_id):
        with transaction(self.engine) as db:
            record = db.get(RecommendationEvent, recommendation_id)
            if record is None or record.learner_id != learner:
                raise PersonalisationError("not_found", "Recommendation not found.", 404)
            if record.status != "shown":
                raise PersonalisationError("invalid_state", "Only a shown suggestion can be dismissed.", 409)
            record.status = "dismissed"
            record.dismissed_at = self.learning.now()
            return {"recommendation_id": record.id, "status": record.status}

    def follow_recommendation(self, learner, recommendation_id):
        with transaction(self.engine) as db:
            record = db.get(RecommendationEvent, recommendation_id)
            if record is None or record.learner_id != learner:
                raise PersonalisationError("not_found", "Recommendation not found.", 404)
            if record.status != "shown":
                raise PersonalisationError("invalid_state", "Only a shown suggestion can be followed.", 409)
            record.status = "followed"
            record.followed_at = self.learning.now()
            return {"recommendation_id": record.id, "status": record.status}
