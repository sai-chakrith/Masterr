"""Deterministic session rules. No model calls or AI-issued grades."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from backend.content import FACETS, available_questions
from backend.db import transaction
from backend.models import Assignment, Attempt, Evidence, Exposure, GapState, Learner, LearningSession, Question, Review
from backend.numbers.bank import compute_answer, load_curriculum

POLICY = "divisibility-check-v1"
RETEST_POLICY = "topic-retest-v1"
SKILLS = {s["id"] for s in load_curriculum()["skills"]}


class LearningError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def uid():
    return str(uuid4())


def utcnow():
    return datetime.now(timezone.utc)


def normalized_integer(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[+-]?[0-9]{1,12}", raw.strip()):
        raise LearningError("invalid_answer", "Enter a whole number of at most 12 digits.", 422)
    value = int(raw.strip())
    if not -(2**31) <= value < 2**31:
        raise LearningError("invalid_answer", "Answer is outside the supported integer range.", 422)
    return value


class LearningService:
    def __init__(self, engine, clock=utcnow):
        self.engine, self.clock = engine, clock

    def now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("Clock must be timezone aware")
        return value.astimezone(timezone.utc).isoformat()

    def lock_learner(self, db, learner):
        record = db.scalar(select(Learner).where(Learner.id == learner).with_for_update())
        if not record:
            raise LearningError("not_found", "Learner not registered.", 404)

    def register(self, learner):
        # Called only after authentication; API identity never comes from a body.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with transaction(self.engine) as db:
            insert = sqlite_insert if self.engine.dialect.name == "sqlite" else pg_insert
            db.execute(insert(Learner).values(id=learner).on_conflict_do_nothing(index_elements=["id"]))

    def owned_session(self, db, learner, session_id):
        session = db.get(LearningSession, session_id)
        if not session or session.learner_id != learner:
            raise LearningError("not_found", "Session not found.", 404)
        return session

    def owned_assignment(self, db, learner, assignment_id):
        assignment = db.get(Assignment, assignment_id)
        if not assignment:
            raise LearningError("not_found", "Assignment not found.", 404)
        session = self.owned_session(db, learner, assignment.session_id)
        return assignment, session

    def assignments(self, db, session_id):
        return list(db.scalars(select(Assignment).where(
            Assignment.session_id == session_id).order_by(Assignment.position)))

    def record_exposure(self, db, learner, assignment, question, kind):
        db.add(Exposure(id=uid(), learner_id=learner, assignment_id=assignment.id,
                        family_id=question.family_id, kind=kind, created_at=self.now()))

    def select_fresh(self, db, learner, skill, purpose, facets=None):
        seen = set(db.scalars(select(Exposure.family_id).where(Exposure.learner_id == learner)))
        selected = []
        candidates = available_questions(db, skill, purpose)
        for facet in (facets or [None]):
            item = next((q for q in candidates if q.family_id not in seen
                         and (facet is None or q.facet == facet)), None)
            if item is None:
                raise LearningError("insufficient_coverage",
                                    "No fresh reviewed coverage is available for this activity.")
            selected.append(item)
            seen.add(item.family_id)
        return selected

    def create_session(self, learner, skill="divisibility", mode="practice", review_id=None, *, retest=False):
        if skill not in SKILLS or mode not in ("diagnostic", "practice", "verification", "review"):
            raise LearningError("invalid_session", "Unknown skill or activity.", 422)
        if not retest and mode in ("verification", "review") and skill != "divisibility":
            raise LearningError("unsupported_policy", "Independent checks currently cover divisibility only.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            active = db.scalar(select(LearningSession).where(
                LearningSession.learner_id == learner, LearningSession.status.in_(["active", "assisted"])))
            if active:
                raise LearningError("active_session", "Resume or abandon your current session first.")
            review = None
            if mode == "review":
                review = db.get(Review, review_id) if review_id else None
                if not review or review.learner_id != learner or review.skill_id != skill:
                    raise LearningError("not_found", "Review not found.", 404)
                if review.status != "pending" or review.due_at > self.now():
                    raise LearningError("review_not_due", "This review is not due.")
            elif review_id:
                raise LearningError("invalid_session", "Review ID is valid only for a review.", 422)
            if retest:
                if mode != "verification" or review_id:
                    raise LearningError("invalid_session", "Retests use independent verification.", 422)
                seen = set(db.scalars(select(Exposure.family_id).where(Exposure.learner_id == learner)))
                candidates = [q for q in available_questions(db, skill, "verification")
                              if q.difficulty_level is not None]
                # Prefer levels 3-4, then nearest tagged levels. Never use hidden or draft items.
                candidates.sort(key=lambda q: (min(abs(q.difficulty_level - 3), abs(q.difficulty_level - 4)), q.id))
                questions = []
                for q in candidates:
                    if q.family_id not in seen:
                        questions.append(q)
                        seen.add(q.family_id)
                    if len(questions) == 10:
                        break
                if len(questions) != 10:
                    raise LearningError("insufficient_coverage", "Retest needs ten fresh reviewed question families with difficulty tags.")
            else:
                questions = self.select_fresh(db, learner, skill,
                    "review" if mode == "review" else mode,
                    FACETS if mode in ("verification", "review") else None)
            policy = RETEST_POLICY if retest else POLICY
            session = LearningSession(id=uid(), learner_id=learner, skill_id=skill,
                mode=mode, policy_version=policy, status="active",
                created_at=self.now(), review_id=review_id)
            db.add(session)
            db.flush()
            for position, question in enumerate(questions):
                assignment = Assignment(id=uid(), session_id=session.id, question_id=question.id,
                    position=position, status="pending", hint_count=0, solution_seen=False)
                db.add(assignment)
                db.flush()
                # Reserve whole forms up front. Conservatively excludes them from later checks.
                self.record_exposure(db, learner, assignment, question, "reserved")
            if review:
                review.status = "in_progress"
            return {"session_id": session.id, "mode": mode, "status": "active",
                    "policy_version": policy, "question_count": len(questions)}

    def get_session(self, learner, session_id):
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            session = self.owned_session(db, learner, session_id)
            assignments = self.assignments(db, session.id)
            pending = next((a for a in assignments if a.status == "pending"), None)
            question_view = None
            if pending and session.status in ("active", "assisted"):
                question = db.get(Question, pending.question_id)
                if question.status != "approved":
                    raise LearningError("content_unavailable", "This question is no longer published.")
                issued = db.scalar(select(Exposure.id).where(
                    Exposure.assignment_id == pending.id, Exposure.kind == "prompt"))
                if not issued:
                    self.record_exposure(db, learner, pending, question, "prompt")
                question_view = {
                    "assignment_id": pending.id, "question_version_id": question.id,
                    "prompt": question.snapshot["prompt"], "difficulty": question.snapshot["difficulty"],
                    "position": pending.position + 1, "facet": question.facet,
                }
            history = []
            if session.status == "completed":
                attempts = db.scalars(select(Attempt).join(Assignment).where(
                    Assignment.session_id == session.id).order_by(Assignment.position))
                history = [{"attempt_id": a.id, "assignment_id": a.assignment_id,
                    "answer": a.raw_answer, "working": a.working, "correct": a.correct,
                    "assistance": a.assistance, "created_at": a.created_at} for a in attempts]
            return {"session_id": session.id, "skill_id": session.skill_id, "mode": session.mode,
                    "status": session.status, "policy_version": session.policy_version,
                    "question_count": len(assignments), "question": question_view, "attempts": history}

    def submit(self, learner, assignment_id, answer, working, key, duration_ms=None, dont_know=False):
        if duration_ms is not None and (type(duration_ms) is not int or not 0 <= duration_ms <= 86400000):
            raise LearningError("invalid_duration", "Duration must be milliseconds between 0 and 86400000.", 422)
        if not key or len(key) > 128 or len(working) > 2000:
            raise LearningError("invalid_submission", "Invalid request key or working length.", 422)
        if type(dont_know) is not bool or (dont_know and answer != ""):
            raise LearningError("invalid_answer", "Use an empty answer when selecting I don't know.", 422)
        value = 0 if dont_know else normalized_integer(answer)
        request_hash = hashlib.sha256(json.dumps(
            [assignment_id, answer, working] + ([] if duration_ms is None else [duration_ms]) + (["dont_know"] if dont_know else []), ensure_ascii=False).encode()).hexdigest()
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            previous = db.scalar(select(Attempt).where(
                Attempt.learner_id == learner, Attempt.idempotency_key == key))
            if previous:
                if previous.request_hash != request_hash:
                    raise LearningError("idempotency_conflict", "Request key was used for different content.")
                return previous.response
            assignment, session = self.owned_assignment(db, learner, assignment_id)
            if assignment.status != "pending" or session.status not in ("active", "assisted"):
                raise LearningError("invalid_state", "This assignment is no longer accepting answers.")
            first = next(a for a in self.assignments(db, session.id) if a.status == "pending")
            issued = db.scalar(select(Exposure.id).where(
                Exposure.assignment_id == assignment.id, Exposure.kind == "prompt"))
            if first.id != assignment.id or not issued:
                raise LearningError("invalid_state", "Open the current question before submitting.")
            question = db.get(Question, assignment.question_id)
            if question.status != "approved":
                raise LearningError("content_unavailable", "Question is no longer published.")
            correct = not dont_know and value == compute_answer(question.snapshot["validator"])
            assistance = "solution_exposed" if assignment.solution_seen else (
                "hinted" if assignment.hint_count or session.status == "assisted" else "independent")
            attempt = Attempt(id=uid(), learner_id=learner, assignment_id=assignment.id,
                idempotency_key=key, request_hash=request_hash, raw_answer="I don't know" if dont_know else answer,
                normalized_answer=value, working=working, correct=correct, assistance=assistance,
                duration_ms=duration_ms, scoring_version="current",
                created_at=self.now(), response={})
            db.add(attempt)
            assignment.status = "submitted"
            db.flush()
            unfinished = any(a.status == "pending" for a in self.assignments(db, session.id))
            response = {"attempt_id": attempt.id, "saved": True, "session_complete": not unfinished}
            if session.mode in ("practice", "diagnostic") or session.status == "assisted":
                response.update(correct=correct, assistance=assistance)
            if not unfinished:
                response.update(self.finish(db, session))
            attempt.response = response
            return response

    def finish(self, db, session):
        attempts = list(db.scalars(select(Attempt).join(Assignment).where(
            Assignment.session_id == session.id).order_by(Assignment.position)))
        if session.status == "assisted":
            result = "assisted_practice"
        elif session.policy_version == RETEST_POLICY:
            passed = len(attempts) == 10 and all(a.assistance == "independent" for a in attempts) and sum(a.correct for a in attempts) >= 7
            result = "retest_passed" if passed else "retest_practice_needed"
            self.set_gap(db, session, "resolved" if passed else "gap")
        elif session.mode in ("verification", "review"):
            passed = len(attempts) == len(FACETS) and all(
                a.correct and a.assistance == "independent" for a in attempts)
            result = ("independent_check_passed" if session.mode == "verification" else
                      "later_check_passed") if passed else "practice_needed"
        else:
            result = "practice_completed" if session.mode == "practice" else "diagnostic_completed"
        if session.policy_version != RETEST_POLICY and session.mode in ("verification", "review") and session.status != "assisted":
            existing_gap = db.get(GapState, (session.learner_id, session.skill_id))
            if existing_gap:
                self.set_gap(db, session, "resolved" if result in ("independent_check_passed", "later_check_passed") else "gap")
        session.status = "completed"
        evidence = Evidence(id=uid(), learner_id=session.learner_id, session_id=session.id,
                            kind=result, policy_version=session.policy_version, created_at=self.now())
        db.add(evidence)
        db.flush()
        if result == "independent_check_passed":
            for day in (2, 7):
                db.add(Review(id=uid(), learner_id=session.learner_id, evidence_id=evidence.id,
                    skill_id=session.skill_id, occasion=day,
                    due_at=(datetime.fromisoformat(self.now()) + timedelta(days=day)).isoformat(),
                    status="pending", completed_at=None))
        if session.review_id:
            review = db.get(Review, session.review_id)
            review.status = "passed" if result == "later_check_passed" else (
                "assisted" if result == "assisted_practice" else "mixed")
            review.completed_at = self.now()
        return {"result": result, "policy_version": session.policy_version,
                "outcomes": [{"attempt_id": a.id, "correct": a.correct,
                              "assistance": a.assistance} for a in attempts]}

    def help(self, learner, assignment_id, kind):
        if kind not in ("hint", "solution"):
            raise LearningError("invalid_help", "Unknown help type.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            assignment, session = self.owned_assignment(db, learner, assignment_id)
            question = db.get(Question, assignment.question_id)
            if question.status != "approved":
                raise LearningError("content_unavailable", "Question is no longer published.")
            issued = db.scalar(select(Exposure.id).where(
                Exposure.assignment_id == assignment.id, Exposure.kind == "prompt"))
            if not issued or assignment.status == "cancelled" or session.status == "abandoned":
                raise LearningError("invalid_state", "Open the current question first.")
            if assignment.status == "submitted":
                if kind != "solution" or session.status != "completed":
                    raise LearningError("invalid_state", "Finish the activity before reviewing solutions.")
            elif session.mode in ("verification", "review"):
                session.status = "assisted"
                for other in self.assignments(db, session.id):
                    if other.id != assignment.id and other.status == "pending":
                        other.status = "cancelled"
            if kind == "hint":
                hints = question.snapshot["hints"]
                if assignment.hint_count >= len(hints):
                    raise LearningError("no_more_hints", "No more reviewed hints are available.")
                text = hints[assignment.hint_count]
                assignment.hint_count += 1
            else:
                text = question.snapshot["solution"]
                assignment.solution_seen = True
            self.record_exposure(db, learner, assignment, question, kind)
            return {"kind": kind, "text": text, "assessment_ended":
                    session.mode in ("verification", "review") and session.status == "assisted"}

    def abandon(self, learner, session_id):
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            session = self.owned_session(db, learner, session_id)
            if session.status not in ("active", "assisted"):
                raise LearningError("invalid_state", "Session has already ended.")
            session.status = "abandoned"
            for item in self.assignments(db, session.id):
                if item.status == "pending":
                    item.status = "cancelled"
            if session.review_id:
                db.get(Review, session.review_id).status = "pending"
            return {"status": "abandoned"}

    def today(self, learner):
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            active = db.scalar(select(LearningSession).where(
                LearningSession.learner_id == learner, LearningSession.status.in_(["active", "assisted"])))
            reviews = list(db.scalars(select(Review).where(
                Review.learner_id == learner).order_by(Review.due_at)))
            evidence = list(db.scalars(select(Evidence).where(
                Evidence.learner_id == learner).order_by(Evidence.created_at)))
            return {"active_session_id": active.id if active else None,
                "reviews": [{"id": r.id, "skill_id": r.skill_id, "occasion": r.occasion,
                    "due_at": r.due_at, "status": r.status,
                    "is_due": r.status == "pending" and r.due_at <= self.now(),
                    "completed_at": r.completed_at} for r in reviews],
                "evidence": [{"id": e.id, "session_id": e.session_id, "kind": e.kind,
                    "policy_version": e.policy_version, "created_at": e.created_at} for e in evidence]}


    def set_gap(self, db, session, status):
        """Track 1 hook: call within its diagnostic-finalization transaction.

        The caller supplies a classification backed by that completed diagnostic;
        no classification thresholds or Elo updates are invented in Track 2.
        """
        if status not in ("mastered", "borderline", "gap", "resolved"):
            raise ValueError("Unknown gap status")
        record = db.get(GapState, (session.learner_id, session.skill_id))
        if record is None:
            record = GapState(learner_id=session.learner_id, skill_id=session.skill_id)
            db.add(record)
        record.status = status
        record.source_session_id = session.id
        record.updated_at = self.now()

    def gaps(self, learner):
        curriculum = load_curriculum()["skills"]
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            records = {g.skill_id: g for g in db.scalars(select(GapState).where(GapState.learner_id == learner))}
            return [{"skill_id": skill["id"], "prerequisites": skill["prerequisites"],
                     "status": records[skill["id"]].status if skill["id"] in records else "unassessed",
                     "source_session_id": records[skill["id"]].source_session_id if skill["id"] in records else None}
                    for skill in curriculum]

    def borderline_review(self, learner, session_id):
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            session = self.owned_session(db, learner, session_id)
            gap = db.get(GapState, (learner, session.skill_id))
            if (session.mode != "diagnostic" or session.status != "completed" or not gap
                    or gap.status != "borderline" or gap.source_session_id != session.id):
                raise LearningError("invalid_state", "A completed Borderline diagnostic is required.")
            items = []
            for assignment in self.assignments(db, session.id):
                attempt = db.scalar(select(Attempt).where(Attempt.assignment_id == assignment.id))
                if attempt and not attempt.correct:
                    question = db.get(Question, assignment.question_id)
                    if question.status != "approved":
                        continue
                    items.append({"assignment_id": assignment.id, "prompt": question.snapshot["prompt"],
                                  "answer": attempt.raw_answer, "solution": question.snapshot["solution"]})
                    if not assignment.solution_seen:
                        assignment.solution_seen = True
                        self.record_exposure(db, learner, assignment, question, "solution")
            return {"session_id": session.id, "items": items, "next_action": "retest", "skill_id": session.skill_id}
