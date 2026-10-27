"""Deterministic session rules. No model calls or AI-issued grades."""
import hashlib
import json
import re
import os
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from backend import mastery
from backend.content import FACETS, available_questions, is_current_question
from backend.db import transaction
from backend.practice import (FIXED_PRACTICE_POLICY, PRACTICE_BLOCK_SIZE, PRACTICE_POLICY,
                              review_days_after_pass, select_adaptive_questions,
                              select_fixed_questions, update_progress)
from backend.models import (Assignment, Attempt, Evidence, Exposure, GapState, Learner, LearnerGoal, LearningProgress,
                            LearningSession, MasteryEstimate, Misconception, Question, QuestionOption, Review, TopicPracticeConfig,
                            TopicScoringConfig)
from backend.numbers.bank import compute_answer, load_curriculum
from backend.app_models import TestExposure, DeletedIdentity
from backend.identity_lock import lock_identity
from backend.mock_state import active_test

POLICY = "divisibility-check-v1"
RETEST_POLICY = "topic-retest-v1"                  # new version (D6)
DIAGNOSTIC_POLICY = "mastery-diagnostic-v2"        # new version (D4)
LEGACY_DIAGNOSTIC_POLICY = "legacy-diagnostic-v0"  # current version: 6 questions, more than half right
LEGACY_RETEST_POLICY = "legacy-retest-v0"          # current version: 3 easiest, 2 of 3
VALIDATION_POLICY = "validation-form-v1"           # pilot Form A / Form B, never followed by feedback
LEGACY_POLICIES = (LEGACY_DIAGNOSTIC_POLICY, LEGACY_RETEST_POLICY)
DIAGNOSTIC_POLICIES = (DIAGNOSTIC_POLICY, LEGACY_DIAGNOSTIC_POLICY)
LEGACY_DIAGNOSTIC_LEVELS = (1, 2, 3, 4, 5, 3)
LEGACY_RETEST_SIZE, LEGACY_RETEST_PASS = 3, 2
VALIDATION_STAGES = {"pre": "A", "post": "B", "delayed": "A"}
VALIDATION_DELAY = timedelta(days=14)
# The diagnostic and retest share one tagged pool, so the diagnostic uses up levels 3-4 (D7).
ASSESSMENT_PURPOSES = ("diagnostic", "verification")
VERSIONS = ("current", "new")
CURRICULUM = load_curriculum()["skills"]
SKILLS = {s["id"] for s in CURRICULUM}


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


def mastery_bar(skill_id, profile=None):
    """Resolve a profile's topic practice target, then the curriculum default."""
    if profile:
        topic_bars = profile.get("topic_bars", {})
        if skill_id in topic_bars:
            return float(topic_bars[skill_id])
        if "default_mastery_bar" in profile:
            return float(profile["default_mastery_bar"])
    skill = next((s for s in CURRICULUM if s["id"] == skill_id), {})
    return float(skill.get("mastery_bar", mastery.BAR))


def learner_mastery_bar(db, learner, skill_id):
    goal = db.get(LearnerGoal, learner)
    return mastery_bar(skill_id, goal.exam_profile_snapshot if goal else None)


def answer_result(attempt):
    if attempt.dont_know:
        return mastery.DONT_KNOW
    return mastery.RIGHT if attempt.correct else mastery.WRONG


def attempt_source(session):
    if session.policy_version in (RETEST_POLICY, LEGACY_RETEST_POLICY):
        return "retest"
    if session.policy_version == VALIDATION_POLICY:
        return "validation"
    return session.mode


class LearningService:
    def __init__(self, engine, clock=utcnow):
        self.engine, self.clock = engine, clock
        self.default_scoring_version = os.environ.get("MASTRR_DEFAULT_SCORING_VERSION", "current")
        if self.default_scoring_version not in VERSIONS:
            raise ValueError("MASTRR_DEFAULT_SCORING_VERSION must be current or new")

    def now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("Clock must be timezone aware")
        return value.astimezone(timezone.utc).isoformat()

    def review_due_at(self, db, learner, interval_days):
        """Keep a scheduled review before the learner's exam date when one is set."""
        now = datetime.fromisoformat(self.now())
        due = now + timedelta(days=interval_days)
        goal = db.get(LearnerGoal, learner)
        if goal and goal.exam_date:
            local_zone = ZoneInfo(goal.timezone)
            exam_day = date.fromisoformat(goal.exam_date)
            latest_review = datetime.combine(
                exam_day - timedelta(days=1), time(hour=9), tzinfo=local_zone
            ).astimezone(timezone.utc)
            if latest_review < now:
                latest_review = now
            due = min(due, latest_review)
        return due.isoformat()

    def check_identity(self, db, learner):
        lock_identity(db, learner)
        if db.get(DeletedIdentity, learner):
            raise LearningError("account_deleted", "This account has been deleted.", 403)

    def score_withheld(self, db, learner, skill):
        active = self.active_session(db, learner)
        return bool(active and active.skill_id == skill and active.mode in ("verification", "review"))

    def lock_learner(self, db, learner):
        self.check_identity(db, learner)
        record = db.scalar(select(Learner).where(Learner.id == learner).with_for_update())
        if not record:
            raise LearningError("not_found", "Learner not registered.", 404)

    def register(self, learner):
        # Called only after authentication; API identity never comes from a body.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with transaction(self.engine) as db:
            self.check_identity(db, learner)
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

    def active_session(self, db, learner):
        return db.scalar(select(LearningSession).where(
            LearningSession.learner_id == learner, LearningSession.status.in_(["active", "assisted"])))

    # ----- question selection -------------------------------------------------------------

    def seen_families(self, db, learner):
        return (set(db.scalars(select(Exposure.family_id).where(Exposure.learner_id == learner)))
                | set(db.scalars(select(TestExposure.family_id).where(TestExposure.learner_id == learner))))

    def tagged_pool(self, db, learner, skill, seen=None):
        """Approved, visible, tagged assessment questions from families the learner never saw."""
        seen = self.seen_families(db, learner) if seen is None else seen
        pool = []
        for purpose in ASSESSMENT_PURPOSES:
            pool += [q for q in available_questions(db, skill, purpose)
                     if q.difficulty_level is not None and q.family_id not in seen]
        return sorted(pool, key=lambda q: q.id)

    @staticmethod
    def take_level(pool, target, seen):
        """K4: the target level, else the nearest level with an unseen family left."""
        ordered = sorted(pool, key=lambda q: (abs(q.difficulty_level - target), q.difficulty_level, q.id))
        item = next((q for q in ordered if q.family_id not in seen), None)
        if item is not None:
            seen.add(item.family_id)
        return item

    def pick_levels(self, db, learner, skill, targets):
        seen = self.seen_families(db, learner)
        pool = self.tagged_pool(db, learner, skill, seen)
        picked = [self.take_level(pool, target, seen) for target in targets]
        return [q for q in picked if q is not None]

    def retest_questions(self, db, learner, skill):
        """S1: ten unseen families, levels 3-4 first, then the nearest tagged levels."""
        seen = self.seen_families(db, learner)
        candidates = self.tagged_pool(db, learner, skill, seen)
        candidates.sort(key=lambda q: (min(abs(q.difficulty_level - 3), abs(q.difficulty_level - 4)), q.id))
        questions = []
        for q in candidates:
            if q.family_id not in seen:
                questions.append(q)
                seen.add(q.family_id)
            if len(questions) == mastery.RETEST_SIZE:
                break
        if len(questions) != mastery.RETEST_SIZE:
            raise LearningError("insufficient_coverage",
                                "Retest needs ten fresh reviewed question families with difficulty tags.")
        return questions

    def select_fresh(self, db, learner, skill, purpose, facets=None):
        seen = self.seen_families(db, learner)
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

    # ----- version switch (D8 / C5) -----------------------------------------------------------

    def version_for(self, db, learner, skill):
        config = db.get(TopicScoringConfig, (learner, skill))
        return config.scoring_version if config else self.default_scoring_version

    def practice_strategy(self, db, learner, skill):
        config = db.get(TopicPracticeConfig, (learner, skill))
        return config.strategy if config else "personalised"

    def set_scoring_version(self, learner, skill, version):
        """Pilot tooling only; students can never choose their own version."""
        if skill not in SKILLS or version not in VERSIONS:
            raise LearningError("invalid_version", "Unknown skill or scoring version.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            config = db.get(TopicScoringConfig, (learner, skill))
            if config is None:
                db.add(TopicScoringConfig(learner_id=learner, skill_id=skill, scoring_version=version))
            else:
                config.scoring_version = version
            return {"learner_id": learner, "skill_id": skill, "scoring_version": version}

    def set_practice_strategy(self, learner, skill, strategy):
        """Pilot assignment only; the learner API does not expose treatment switching."""
        if skill not in SKILLS or strategy not in ("personalised", "fixed"):
            raise LearningError("invalid_strategy", "Unknown skill or practice strategy.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            config = db.get(TopicPracticeConfig, (learner, skill))
            if config is None:
                db.add(TopicPracticeConfig(learner_id=learner, skill_id=skill, strategy=strategy))
            else:
                config.strategy = strategy
            return {"learner_id": learner, "skill_id": skill, "practice_strategy": strategy}

    # ----- sessions ------------------------------------------------------------------------------

    def create_session(self, learner, skill="divisibility", mode="practice", review_id=None, *, retest=False):
        if skill not in SKILLS or mode not in ("diagnostic", "practice", "verification", "review"):
            raise LearningError("invalid_session", "Unknown skill or activity.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            if self.active_session(db, learner) or active_test(db, learner):
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
            version = self.version_for(db, learner, skill)
            if not retest and mode in ("verification", "review") and skill != "divisibility" and version != "new":
                raise LearningError("unsupported_policy",
                                    "Independent checks for this topic require the new scoring policy.", 422)
            policy = POLICY
            if retest:
                if mode != "verification" or review_id:
                    raise LearningError("invalid_session", "Retests use independent verification.", 422)
                if version == "new":
                    policy, questions = RETEST_POLICY, self.retest_questions(db, learner, skill)
                else:
                    policy = LEGACY_RETEST_POLICY
                    seen = self.seen_families(db, learner)
                    pool = self.tagged_pool(db, learner, skill, seen)
                    questions = [self.take_level(pool, 1, seen) for _ in range(LEGACY_RETEST_SIZE)]
                    if None in questions:
                        raise LearningError("insufficient_coverage",
                                            "Retest needs three fresh tagged question families.")
            elif mode == "diagnostic":
                if db.get(GapState, (learner, skill)):
                    raise LearningError("already_assessed", "This topic already has a diagnostic decision.")
                if version == "new":
                    policy = DIAGNOSTIC_POLICY
                    targets = [mastery.diagnostic_level(i) for i in range(mastery.DIAGNOSTIC_MIN)]
                else:
                    policy, targets = LEGACY_DIAGNOSTIC_POLICY, LEGACY_DIAGNOSTIC_LEVELS
                questions = self.pick_levels(db, learner, skill, targets)
                if len(questions) != len(targets):
                    raise LearningError("insufficient_coverage",
                                        "The diagnostic needs more fresh tagged question families.")
            elif mode == "practice":
                strategy = self.practice_strategy(db, learner, skill)
                seen = self.seen_families(db, learner)
                candidates = [q for q in available_questions(db, skill, "practice")
                              if q.family_id not in seen]
                tagged = [q for q in candidates if q.difficulty_level is not None]
                if not tagged:
                    # Preserve the original one-question loop for legacy banks without
                    # difficulty tags. Such banks cannot support a defensible adaptive pick.
                    questions = self.select_fresh(db, learner, skill, "practice")
                    policy = POLICY
                elif strategy == "personalised":
                    estimate = db.get(MasteryEstimate, (learner, skill))
                    if estimate and estimate.answer_count:
                        rating = estimate.rating
                    else:
                        evidence_rows = list(db.execute(select(Question.difficulty_level, Attempt).join(
                            Assignment, Assignment.question_id == Question.id).join(
                            LearningSession, LearningSession.id == Assignment.session_id).join(
                            Attempt, Attempt.assignment_id == Assignment.id).where(
                            LearningSession.learner_id == learner,
                            LearningSession.skill_id == skill,
                            Attempt.assistance == "independent",
                            Question.difficulty_level.is_not(None),
                        )))
                        rating = mastery.rescore((level, answer_result(attempt))
                                                 for level, attempt in evidence_rows) if evidence_rows else 0.0
                    questions = select_adaptive_questions(tagged, rating, PRACTICE_BLOCK_SIZE)
                    policy = PRACTICE_POLICY
                else:
                    questions = select_fixed_questions(tagged, PRACTICE_BLOCK_SIZE)
                    policy = FIXED_PRACTICE_POLICY
                if not questions:
                    raise LearningError("insufficient_coverage",
                                        "No fresh reviewed practice questions are available.")
            else:
                questions = self.select_fresh(db, learner, skill,
                    "review" if mode == "review" else mode,
                    FACETS if mode in ("verification", "review") else None)
            session = self.start(db, learner, skill, mode, policy, version, questions, review_id=review_id)
            if mode == "practice":
                progress = db.get(LearningProgress, (learner, skill))
                if progress is None:
                    progress = LearningProgress(
                        learner_id=learner, skill_id=skill, phase="practice",
                        practice_count=0, best_probability=None, no_progress_count=0,
                        recent_probabilities=[], stuck=False, policy_version=policy,
                        updated_at=self.now(),
                    )
                    db.add(progress)
                else:
                    progress.phase = "practice"
                    progress.stuck = False
                    progress.policy_version = policy
                    progress.updated_at = self.now()
            if review:
                review.status = "in_progress"
            return {"session_id": session.id, "mode": mode, "status": "active", "scoring_version": version,
                    "policy_version": policy, "question_count": len(questions)}

    def start(self, db, learner, skill, mode, policy, version, questions, review_id=None, stage=None):
        session = LearningSession(id=uid(), learner_id=learner, skill_id=skill,
            mode=mode, policy_version=policy, status="active", scoring_version=version,
            stage=stage, created_at=self.now(), review_id=review_id)
        db.add(session)
        db.flush()
        for position, question in enumerate(questions):
            self.add_assignment(db, session, question, position)
        return session

    def add_assignment(self, db, session, question, position):
        assignment = Assignment(id=uid(), session_id=session.id, question_id=question.id,
            position=position, status="pending", hint_count=0, solution_seen=False)
        db.add(assignment)
        db.flush()
        # Reserve whole forms up front. Conservatively excludes them from later checks.
        self.record_exposure(db, session.learner_id, assignment, question, "reserved")
        return assignment

    def create_validation(self, learner, skill):
        """Pilot test: Form A before the topic, Form B when it ends, Form A again a week later."""
        if skill not in SKILLS:
            raise LearningError("invalid_session", "Unknown skill or activity.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            if self.active_session(db, learner) or active_test(db, learner):
                raise LearningError("active_session", "Resume or abandon your current session first.")
            done = list(db.scalars(select(LearningSession).where(
                LearningSession.learner_id == learner, LearningSession.skill_id == skill,
                LearningSession.policy_version == VALIDATION_POLICY,
                LearningSession.status == "completed").order_by(LearningSession.created_at)))
            stage = ("pre", "post", "delayed", None)[min(len(done), 3)]
            if stage is None:
                raise LearningError("validation_complete", "All three validation tests are complete.")
            topic_work = db.scalar(select(LearningSession.id).where(
                LearningSession.learner_id == learner, LearningSession.skill_id == skill,
                LearningSession.policy_version != VALIDATION_POLICY))
            gap = db.get(GapState, (learner, skill))
            if stage == "pre" and topic_work:
                raise LearningError("validation_order", "The pre-test must come before any work on this topic.")
            if stage == "post" and (not gap or gap.status not in ("mastered", "resolved")):
                raise LearningError("validation_order", "The post-test opens when the topic ends.")
            if stage == "delayed":
                finished = db.scalar(select(Evidence.created_at).where(Evidence.session_id == done[-1].id))
                if datetime.fromisoformat(self.now()) < datetime.fromisoformat(finished) + VALIDATION_DELAY:
                    raise LearningError("validation_not_due", "The delayed test opens two weeks after the post-test.")
            form = VALIDATION_STAGES[stage]
            questions = [q for q in db.scalars(select(Question).where(
                Question.skill_id == skill, Question.status == "approved", Question.hidden.is_(True)
            ).order_by(Question.difficulty_level, Question.id)) if q.snapshot.get("validation_form") == form]
            if not questions:
                raise LearningError("insufficient_coverage", "No reviewed validation form is available for this topic.")
            version = self.version_for(db, learner, skill)
            session = self.start(db, learner, skill, "verification", VALIDATION_POLICY, version, questions,
                                 stage=stage)
            return {"session_id": session.id, "mode": "verification", "status": "active", "stage": stage,
                    "form": form, "scoring_version": version, "policy_version": VALIDATION_POLICY,
                    "question_count": len(questions)}

    def get_session(self, learner, session_id):
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            session = self.owned_session(db, learner, session_id)
            assignments = self.assignments(db, session.id)
            pending = next((a for a in assignments if a.status == "pending"), None)
            question_view = None
            if pending and session.status in ("active", "assisted"):
                question = db.get(Question, pending.question_id)
                if not is_current_question(db, question):
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
                options = list(db.scalars(select(QuestionOption).where(
                    QuestionOption.question_id == question.id).order_by(QuestionOption.position)))
                if options:
                    question_view["options"] = [{"id": option.option_id, "text": option.text}
                                                 for option in options]
            history = []
            completion = None
            if session.status == "completed":
                attempts = list(db.scalars(select(Attempt).join(Assignment).where(
                    Assignment.session_id == session.id).order_by(Assignment.position)))
                if attempts:
                    fields = ("result", "decision", "score", "answers", "outcomes")
                    if session.policy_version == VALIDATION_POLICY:
                        fields = ("result",)
                    completion = {"saved": True, "session_complete": True,
                                  **{k: v for k, v in (attempts[-1].response or {}).items() if k in fields}}
                history = [{"attempt_id": a.id, "assignment_id": a.assignment_id,
                    "answer": a.raw_answer, "working": a.working, "correct": a.correct,
                    "assistance": a.assistance, "created_at": a.created_at} for a in attempts]
                if session.policy_version == VALIDATION_POLICY:
                    for item in history:
                        del item["correct"]  # validation forms are never followed by feedback
            return {"session_id": session.id, "skill_id": session.skill_id, "mode": session.mode,
                    "status": session.status, "policy_version": session.policy_version,
                    "scoring_version": session.scoring_version, "stage": session.stage,
                    "question_count": len(assignments), "question": question_view, "attempts": history,
                    "completion": completion}

    def submit(self, learner, assignment_id, answer, working, key, duration_ms=None, dont_know=False,
               option_id=None):
        if duration_ms is not None and (type(duration_ms) is not int or not 0 <= duration_ms <= 86400000):
            raise LearningError("invalid_duration", "Duration must be milliseconds between 0 and 86400000.", 422)
        if not key or len(key) > 128 or len(working) > 2000:
            raise LearningError("invalid_submission", "Invalid request key or working length.", 422)
        if (type(dont_know) is not bool or (dont_know and (answer != "" or option_id is not None))
                or (option_id is not None and answer != "")):
            raise LearningError("invalid_answer", "Use an empty answer when selecting I don't know.", 422)
        value = 0 if dont_know or option_id is not None else normalized_integer(answer)
        request_hash = hashlib.sha256(json.dumps(
            [assignment_id, answer, working] + ([] if duration_ms is None else [duration_ms])
            + (["dont_know"] if dont_know else []) + (["option", option_id] if option_id is not None else []),
            ensure_ascii=False).encode()).hexdigest()
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
            if not is_current_question(db, question):
                raise LearningError("content_unavailable", "Question is no longer published.")
            if dont_know and session.policy_version in LEGACY_POLICIES:
                raise LearningError("invalid_answer", "This version has no I don't know option.", 422)
            options = list(db.scalars(select(QuestionOption).where(
                QuestionOption.question_id == question.id).order_by(QuestionOption.position)))
            selected_option = None
            misconception_id = None
            if options:
                if option_id is not None:
                    selected_option = next((option for option in options if option.option_id == option_id), None)
                    if selected_option is None:
                        raise LearningError("invalid_answer", "Choose one of the displayed options.", 422)
                    # Keep the chosen numeric value for the audit trail. Position is
                    # presentation order and must not change the recorded answer.
                    value = selected_option.value
                    misconception_id = selected_option.misconception_id
                elif not dont_know:
                    raise LearningError("invalid_answer", "Select an answer option or choose I don't know.", 422)
                correct = bool(selected_option and selected_option.is_correct)
            else:
                if option_id is not None:
                    raise LearningError("invalid_answer", "This question uses a typed integer answer.", 422)
                correct = not dont_know and value == compute_answer(question.snapshot["validator"])
            prior_misconception_count = 0
            if misconception_id and not correct:
                prior_misconception_count = db.scalar(select(func.count(Attempt.id)).where(
                    Attempt.learner_id == learner,
                    Attempt.misconception_id == misconception_id,
                    Attempt.correct.is_(False),
                )) or 0
            assistance = "solution_exposed" if assignment.solution_seen else (
                "hinted" if assignment.hint_count or session.status == "assisted" else "independent")
            attempt = Attempt(id=uid(), learner_id=learner, assignment_id=assignment.id,
                idempotency_key=key, request_hash=request_hash,
                raw_answer="I don't know" if dont_know else (option_id if option_id is not None else answer),
                normalized_answer=value, selected_option_id=option_id, misconception_id=misconception_id,
                working=working, correct=correct, assistance=assistance,
                duration_ms=duration_ms, scoring_version=session.scoring_version,
                source=attempt_source(session), dont_know=dont_know,
                created_at=self.now(), response={})
            db.add(attempt)
            assignment.status = "submitted"
            self.score_answer(db, session, question, attempt)
            if (session.policy_version in (PRACTICE_POLICY, FIXED_PRACTICE_POLICY)
                    and attempt.assistance == "independent"):
                progress = db.get(LearningProgress, (learner, session.skill_id))
                if progress is None:
                    progress = LearningProgress(
                        learner_id=learner, skill_id=session.skill_id,
                        phase="practice", practice_count=0, best_probability=None,
                        no_progress_count=0, recent_probabilities=[], stuck=False,
                        policy_version=session.policy_version, updated_at=self.now(),
                    )
                    db.add(progress)
                if session.scoring_version == "new":
                    estimate = self.estimate(db, learner, session.skill_id)
                    current_score = mastery.shown_score(estimate.rating)
                else:
                    session_attempts = list(db.scalars(select(Attempt).join(Assignment).where(
                        Assignment.session_id == session.id,
                        Attempt.assistance == "independent")))
                    current_score = sum(item.correct for item in session_attempts) / len(session_attempts)
                state = update_progress(
                    count=progress.practice_count,
                    best_score=progress.best_probability,
                    recent_scores=progress.recent_probabilities or [],
                    score=current_score,
                    mastery_bar=learner_mastery_bar(db, learner, session.skill_id),
                )
                progress.practice_count = state.count
                progress.best_probability = state.best_score
                progress.recent_probabilities = list(state.recent_scores)
                progress.stuck = state.stuck
                progress.phase = "ready_for_retest" if state.ready_for_retest else (
                    "stuck" if state.stuck else "practice")
                progress.policy_version = session.policy_version
                progress.updated_at = self.now()
                if state.ready_for_retest and session.policy_version == PRACTICE_POLICY:
                    for pending in self.assignments(db, session.id):
                        if pending.status == "pending":
                            pending.status = "cancelled"
            db.flush()
            if session.policy_version == DIAGNOSTIC_POLICY:
                self.extend_diagnostic(db, session)
            unfinished = any(a.status == "pending" for a in self.assignments(db, session.id))
            response = {"attempt_id": attempt.id, "saved": True, "session_complete": not unfinished}
            if session.mode in ("practice", "diagnostic") or session.status == "assisted":
                response.update(correct=correct, assistance=assistance)
            if session.mode == "practice" and not correct:
                response["explanation"] = question.snapshot["solution"]
            if (misconception_id and not correct and session.mode not in ("verification", "review")
                    and session.policy_version != VALIDATION_POLICY):
                misconception = db.get(Misconception, misconception_id)
                if misconception:
                    feedback = {"id": misconception.id, "description": misconception.description,
                                "short_fix": misconception.short_fix,
                                "occurrence_count": prior_misconception_count + 1,
                                "targeted_reset": prior_misconception_count >= 1}
                    response["misconception_feedback"] = feedback
            if not unfinished:
                response.update(self.finish(db, session))
            attempt.response = response
            return response

    # ----- scoring (Track 1 engine wired into every answer) -------------------------------------

    def estimate(self, db, learner, skill):
        record = db.get(MasteryEstimate, (learner, skill))
        if record is None:
            record = MasteryEstimate(learner_id=learner, skill_id=skill, rating=0.0,
                                     answer_count=0, recent_changes=[])
            db.add(record)
        return record

    def score_answer(self, db, session, question, attempt):
        """D2: every new-version answer moves the running rating; the current version is untouched.

        Validation answers store the prediction but never move the rating. Help-assisted and
        untagged answers are saved without counting as evidence.
        """
        if session.scoring_version != "new" or question.difficulty_level is None:
            return
        record = self.estimate(db, session.learner_id, session.skill_id)
        if attempt.source == "validation" or attempt.assistance != "independent":
            attempt.predicted_probability = mastery.expected(record.rating, question.difficulty_level)
            return
        step = mastery.update(record.rating, record.answer_count, record.recent_changes or [],
                              question.difficulty_level, answer_result(attempt))
        attempt.predicted_probability = step.expected
        record.rating, record.answer_count, record.recent_changes = step.rating, step.answer_count, step.recent_changes

    def diagnostic_answers(self, db, session):
        rows = db.execute(select(Question.difficulty_level, Attempt).join(
            Assignment, Assignment.question_id == Question.id).join(
            Attempt, Attempt.assignment_id == Assignment.id).where(
            Assignment.session_id == session.id).order_by(Assignment.position))
        return [(level, answer_result(attempt)) for level, attempt in rows]

    def extend_diagnostic(self, db, session):
        """D4 safety zone: after 8 answers add one question at a time while undecided, up to 12."""
        assignments = self.assignments(db, session.id)
        if any(a.status == "pending" for a in assignments):
            return
        if mastery.decide(self.diagnostic_answers(db, session)).status != "continue":
            return
        position = len(assignments)
        picked = self.pick_levels(db, session.learner_id, session.skill_id, [mastery.diagnostic_level(position)])
        if picked:  # an exhausted bank ends the diagnostic as Borderline in finish()
            self.add_assignment(db, session, picked[0], position)

    def finish(self, db, session):
        attempts = list(db.scalars(select(Attempt).join(Assignment).where(
            Assignment.session_id == session.id).order_by(Assignment.position)))
        extra = {}
        if session.status == "assisted":
            result = "assisted_practice"
        elif session.policy_version == RETEST_POLICY:
            passed = mastery.retest_passed(
                answer_result(a) if a.assistance == "independent" else mastery.WRONG for a in attempts)
            result = "retest_passed" if passed else "retest_practice_needed"
            self.set_gap(db, session, "resolved" if passed else "gap")
        elif session.policy_version == LEGACY_RETEST_POLICY:
            passed = (len(attempts) == LEGACY_RETEST_SIZE and all(a.assistance == "independent" for a in attempts)
                      and sum(a.correct for a in attempts) >= LEGACY_RETEST_PASS)
            result = "retest_passed" if passed else "retest_practice_needed"
            self.set_gap(db, session, "resolved" if passed else "gap")
        elif session.policy_version == DIAGNOSTIC_POLICY:
            decision = mastery.decide(self.diagnostic_answers(db, session))
            status = "borderline" if decision.status == "continue" else decision.status
            # The running score continues from the re-score; order of answers no longer matters.
            self.estimate(db, session.learner_id, session.skill_id).rating = decision.rating
            self.set_gap(db, session, status)
            result = "diagnostic_" + status
            extra = {"decision": status, "score": round(decision.score, 4), "answers": decision.answers}
        elif session.policy_version == LEGACY_DIAGNOSTIC_POLICY:
            status = "mastered" if sum(a.correct for a in attempts) / len(attempts) > 0.5 else "gap"
            self.set_gap(db, session, status)
            result = "diagnostic_" + status
            extra = {"decision": status}
        elif session.policy_version == VALIDATION_POLICY:
            result = "validation_completed"
        elif session.mode in ("verification", "review"):
            passed = len(attempts) == len(FACETS) and all(
                a.correct and a.assistance == "independent" for a in attempts)
            result = ("independent_check_passed" if session.mode == "verification" else
                      "later_check_passed") if passed else "practice_needed"
        else:
            result = "practice_completed" if session.mode == "practice" else "diagnostic_completed"
        if session.policy_version == POLICY and session.mode in ("verification", "review") and session.status != "assisted":
            existing_gap = db.get(GapState, (session.learner_id, session.skill_id))
            if existing_gap:
                self.set_gap(db, session, "resolved" if result in ("independent_check_passed", "later_check_passed") else "gap")
        progress = db.get(LearningProgress, (session.learner_id, session.skill_id))
        if progress and session.policy_version in (RETEST_POLICY, LEGACY_RETEST_POLICY):
            progress.phase = "review" if result == "retest_passed" else "practice"
            progress.stuck = False
            progress.updated_at = self.now()
        elif progress and session.mode == "review":
            progress.phase = "review" if result == "later_check_passed" else "practice"
            progress.stuck = False
            progress.updated_at = self.now()
        session.status = "completed"
        evidence = Evidence(id=uid(), learner_id=session.learner_id, session_id=session.id,
                            kind=result, policy_version=session.policy_version, created_at=self.now())
        db.add(evidence)
        db.flush()
        if result in ("independent_check_passed", "retest_passed", "diagnostic_mastered"):
            if result == "retest_passed":
                for old_review in db.scalars(select(Review).where(Review.learner_id == session.learner_id,
                        Review.skill_id == session.skill_id, Review.status == "pending")):
                    old_review.status = "superseded"
            interval = review_days_after_pass(0)
            if interval is not None:
                db.add(Review(id=uid(), learner_id=session.learner_id, evidence_id=evidence.id,
                    skill_id=session.skill_id, occasion=0,
                    due_at=self.review_due_at(db, session.learner_id, interval),
                    status="pending", completed_at=None))
        if session.review_id:
            review = db.get(Review, session.review_id)
            review.status = "passed" if result == "later_check_passed" else (
                "assisted" if result == "assisted_practice" else "mixed")
            review.completed_at = self.now()
            if result == "later_check_passed":
                interval = review_days_after_pass(review.occasion + 1)
                if interval is not None:
                    db.add(Review(id=uid(), learner_id=session.learner_id, evidence_id=evidence.id,
                        skill_id=session.skill_id, occasion=review.occasion + 1,
                        due_at=self.review_due_at(db, session.learner_id, interval),
                        status="pending", completed_at=None))
        if session.policy_version == VALIDATION_POLICY:
            return {"result": result, "policy_version": session.policy_version, "stage": session.stage}
        return {"result": result, "policy_version": session.policy_version, **extra,
                "outcomes": [{"attempt_id": a.id, "correct": a.correct,
                              "assistance": a.assistance} for a in attempts]}

    def help(self, learner, assignment_id, kind):
        if kind not in ("hint", "solution"):
            raise LearningError("invalid_help", "Unknown help type.", 422)
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            assignment, session = self.owned_assignment(db, learner, assignment_id)
            question = db.get(Question, assignment.question_id)
            if not is_current_question(db, question):
                raise LearningError("content_unavailable", "Question is no longer published.")
            issued = db.scalar(select(Exposure.id).where(
                Exposure.assignment_id == assignment.id, Exposure.kind == "prompt"))
            if not issued or assignment.status == "cancelled" or session.status == "abandoned":
                raise LearningError("invalid_state", "Open the current question first.")
            if session.policy_version == VALIDATION_POLICY:
                raise LearningError("invalid_state", "Validation tests have no hints or solutions.")
            if session.policy_version in DIAGNOSTIC_POLICIES and session.status != "completed":
                raise LearningError("invalid_state", "Help opens after the diagnostic ends.")
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
            active = self.active_session(db, learner)
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

    # ----- gaps (Track 2) and dashboard ------------------------------------------------------------

    def assessment_stale(self, db, session_id):
        questions = db.scalars(select(Question).join(Assignment, Assignment.question_id == Question.id)
                               .where(Assignment.session_id == session_id))
        return any(not is_current_question(db, question) for question in questions)

    def set_gap(self, db, session, status):
        """Record an assessment-backed decision inside the deciding session's transaction.

        Only diagnostics, retests and independent checks call this. Reading /gaps and
        movements of the running score never change a decision (D6).
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
        with transaction(self.engine) as db:
            self.lock_learner(db, learner)
            goal = db.get(LearnerGoal, learner)
            profile = goal.exam_profile_snapshot if goal else None
            records = {g.skill_id: g for g in db.scalars(select(GapState).where(GapState.learner_id == learner))}
            estimates = {e.skill_id: e for e in db.scalars(select(MasteryEstimate).where(
                MasteryEstimate.learner_id == learner))}
            configs = {c.skill_id: c.scoring_version for c in db.scalars(select(TopicScoringConfig).where(
                TopicScoringConfig.learner_id == learner))}
            active = self.active_session(db, learner)
            result = []
            for skill in CURRICULUM:
                sid, version = skill["id"], configs.get(skill["id"], self.default_scoring_version)
                record, estimate = records.get(sid), estimates.get(sid)
                stale = bool(record and self.assessment_stale(db, record.source_session_id))
                # A moving score would reveal answers inside a form that withholds feedback.
                withheld = stale or bool(active and active.skill_id == sid and active.mode in ("verification", "review"))
                counted = estimate.answer_count if estimate and version == "new" else 0
                score = None
                if counted and not withheld:
                    score = round(mastery.shown_score(estimate.rating), 4)
                result.append({"skill_id": sid, "title": skill["title"], "prerequisites": skill["prerequisites"],
                               "status": record.status if record and not stale else "unassessed",
                               "previous_status": record.status if stale else None, "evidence_stale": stale,
                               "source_session_id": record.source_session_id if record else None,
                               "scoring_version": version, "score": score, "answer_count": counted,
                               "mastery_bar": mastery_bar(sid, profile), "score_withheld": withheld})
            return result

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
                    if not is_current_question(db, question):
                        continue
                    items.append({"assignment_id": assignment.id, "prompt": question.snapshot["prompt"],
                                  "answer": attempt.raw_answer, "dont_know": attempt.dont_know,
                                  "solution": question.snapshot["solution"]})
                    if not assignment.solution_seen:
                        assignment.solution_seen = True
                        self.record_exposure(db, learner, assignment, question, "solution")
            return {"session_id": session.id, "items": items, "next_action": "retest", "skill_id": session.skill_id}
