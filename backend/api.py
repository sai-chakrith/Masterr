"""First learning-loop API. Run on loopback only when using local development."""
from typing import Annotated, Literal
import os

from fastapi import Depends, FastAPI, Header, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import Settings, make_identity
from backend.db import make_engine
from backend.learning import LearningError, LearningService
from backend.tutor import TutorService
from backend.personalisation import PersonalisationError, PersonalisationService
from backend.curriculum import load_curriculum
from backend.exam_profiles import approved_profiles, load_exam_profiles
from backend.publication import load_document
from backend.operations import AccountService, BudgetService
from backend.review import ReviewService
from backend.app_models import DeletedIdentity
from backend.db import transaction
from sqlalchemy import select, text
from backend.http_safety import RequestSafetyMiddleware
from backend.timed_practice import TimedPracticeService


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionBody(StrictBody):
    skill_id: str = Field(default="divisibility", max_length=128)
    mode: Literal["diagnostic", "practice", "verification", "review"] = "practice"
    review_id: str | None = Field(default=None, max_length=36)


class Submission(StrictBody):
    answer: str = Field(default="", max_length=32)
    option_id: str | None = Field(default=None, max_length=128)
    dont_know: bool = Field(default=False, strict=True)
    working: str = Field(default="", max_length=2000)
    duration_ms: int | None = Field(default=None, ge=0, le=86400000, strict=True)


class HelpBody(StrictBody):
    kind: Literal["hint", "solution"]


class GoalBody(StrictBody):
    target_skill_ids: list[str] = Field(default_factory=list, max_length=35)
    exam_profile_id: str | None = Field(default=None, max_length=128)
    exam_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    timezone: str = Field(default="Asia/Kolkata", max_length=64)


class RecommendationBody(StrictBody):
    state_fingerprint: str = Field(min_length=64, max_length=64)
    action_index: int = Field(default=0, ge=0, le=2, strict=True)


class ReviewBody(StrictBody):
    action: Literal["save", "approve", "withdraw"]
    expected_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    document: dict | None = None
    note: str = Field(default="", max_length=2000)
    confirm_reviewed: bool = Field(default=False, strict=True)


class ReportBody(StrictBody):
    message: str = Field(min_length=10, max_length=2000)


class DeleteBody(StrictBody):
    confirmation: Literal["DELETE"]


class CompleteTutoringBody(StrictBody):
    tutoring_id: str = Field(min_length=1, max_length=36)


class ResolutionBody(StrictBody):
    resolution: str = Field(min_length=10, max_length=2000)


class TimedTestBody(StrictBody):
    skill_ids: list[str] = Field(min_length=1, max_length=15)
    question_count: int = Field(default=10, ge=3, le=30, strict=True)
    minutes: int = Field(default=15, ge=1, le=120, strict=True)


class TimedAnswerBody(StrictBody):
    question_id: str = Field(min_length=1, max_length=128)
    answer: str = Field(default="", max_length=32)
    option_id: str | None = Field(default=None, max_length=128)
    dont_know: bool = Field(default=False, strict=True)


def create_app(engine=None, settings=None):
    if settings is None and os.environ.get("LOCAL_DEVELOPMENT") == "1":
        from backend.local_env import load_local_env
        load_local_env()
    settings = settings or Settings.from_env()
    if os.environ.get("MASTRR_ENV") == "production" and settings.local_development:
        raise ValueError("Production cannot use local developer authentication.")
    engine = engine or make_engine(settings.database_url)
    demo_mode = os.environ.get("MASTRR_DEMO") == "1"
    if demo_mode:
        if not settings.local_development:
            raise ValueError("Demo mode requires explicit local development authentication.")
        from backend.demo import assert_demo_database
        assert_demo_database(engine)
    service = LearningService(engine)
    tutor_service = TutorService(engine)
    personalisation = PersonalisationService(engine, service)
    accounts, budget, reviews = AccountService(engine, settings), BudgetService(engine), ReviewService(engine)
    timed_practice = TimedPracticeService(engine, service)
    app = FastAPI(title="Mastrr learning API", version="0.1.0")
    app.add_middleware(RequestSafetyMiddleware)
    app.state.service = service
    app.state.tutor = tutor_service
    app.state.personalisation = personalisation
    app.state.accounts = accounts
    authenticate = make_identity(settings)

    def learner(subject: Annotated[str, Depends(authenticate)]):
        with transaction(engine) as db:
            if db.get(DeletedIdentity, subject):
                raise HTTPException(status_code=403, detail="This account has been deleted.")
        budget.rate_limit(subject)
        service.register(subject)
        return subject

    def reviewer(owner: Annotated[str, Depends(learner)]):
        if owner not in settings.admin_subjects:
            raise HTTPException(status_code=403, detail="Content reviewer access required.")
        return owner

    @app.exception_handler(LearningError)
    def domain_error(request: Request, error: LearningError):
        return JSONResponse(status_code=error.status, headers={"Retry-After": "60"} if error.status == 429 else None,
                            content={"error": {"code": error.code, "message": error.message}})

    @app.exception_handler(PersonalisationError)
    def personalisation_error(request: Request, error: PersonalisationError):
        return JSONResponse(status_code=error.status,
                            content={"error": {"code": error.code, "message": error.message}})

    @app.get("/v1/curriculum")
    def curriculum(owner: Annotated[str, Depends(learner)]):
        document = load_document(engine, "curriculum", load_curriculum)
        return {
            "id": document["id"],
            "version": str(document.get("schema_version", "1")),
            "status": document.get("status", "draft"),
            "skills": [
                {"id": s["id"], "title": s["title"], "prerequisites": s["prerequisites"],
                 "objective": s.get("objective") if document.get("status") == "approved" else None,
                 "lesson": s.get("lesson") if document.get("status") == "approved" else None}
                for s in document["skills"]
            ],
            "exam_profiles": [
                {"id": profile["id"], "name": profile["name"],
                 "target_skill_ids": profile["target_skill_ids"],
                 "default_mastery_bar": profile.get("default_mastery_bar", 0.75),
                 "topic_bars": profile.get("topic_bars", {})}
                for profile in approved_profiles(load_document(engine, "exam-profiles", load_exam_profiles))
            ],
        }

    @app.get("/v1/me/goal")
    def get_goal(owner: Annotated[str, Depends(learner)]):
        return personalisation.get_goal(owner)

    @app.put("/v1/me/goal")
    def set_goal(body: GoalBody, owner: Annotated[str, Depends(learner)]):
        return personalisation.set_goal(owner, body.target_skill_ids, body.exam_date,
                                        body.timezone, body.exam_profile_id)

    @app.get("/v1/me/next-action")
    def next_action(owner: Annotated[str, Depends(learner)]):
        return personalisation.next_action(owner)

    @app.get("/v1/me/roadmap")
    def roadmap(owner: Annotated[str, Depends(learner)]):
        return personalisation.roadmap(owner)

    @app.get("/v1/me/teaching/{skill_id}")
    def teaching(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return personalisation.teaching(owner, skill_id)

    @app.post("/v1/me/recommendations", status_code=201)
    def record_recommendation(body: RecommendationBody, owner: Annotated[str, Depends(learner)]):
        return personalisation.record_recommendation(owner, body.state_fingerprint, body.action_index)

    @app.post("/v1/me/recommendations/{recommendation_id}/dismiss")
    def dismiss_recommendation(recommendation_id: str, owner: Annotated[str, Depends(learner)]):
        return personalisation.dismiss_recommendation(owner, recommendation_id)

    @app.post("/v1/me/recommendations/{recommendation_id}/follow")
    def follow_recommendation(recommendation_id: str, owner: Annotated[str, Depends(learner)]):
        return personalisation.follow_recommendation(owner, recommendation_id)

    @app.get("/v1/me/gaps")
    def gaps(owner: Annotated[str, Depends(learner)]):
        return service.gaps(owner)

    @app.post("/v1/topics/{skill_id}/retest", status_code=201)
    def retest(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return service.create_session(owner, skill_id, "verification", retest=True)

    @app.post("/v1/topics/{skill_id}/validation", status_code=201)
    def validation(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return service.create_validation(owner, skill_id)

    @app.get("/v1/sessions/{session_id}/borderline-review")
    def borderline_review(session_id: str, owner: Annotated[str, Depends(learner)]):
        return service.borderline_review(owner, session_id)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0", "ai_enabled": bool(tutor_service.settings.api_key)}

    @app.get("/runtime")
    def runtime():
        return JSONResponse(content={"demo": demo_mode, "ai_configured": bool(tutor_service.settings.api_key)}, headers={"Cache-Control": "no-store"})

    @app.post("/v1/me/tutor/{skill_id}")
    def tutor(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return app.state.tutor.tutor(owner, skill_id)

    @app.get("/v1/me/tutor/topics")
    def tutor_topics(owner: Annotated[str, Depends(learner)]):
        from backend.numbers.bank import load_curriculum as tutor_curriculum
        return [{"id": s["id"], "title": s["title"]} for s in tutor_curriculum()["skills"]]

    @app.post("/v1/me/tutor/{skill_id}/complete")
    def complete_tutoring(skill_id: str, body: CompleteTutoringBody, owner: Annotated[str, Depends(learner)]):
        from backend.models import LearningProgress
        from backend.tutor_models import TutoringRecord
        with transaction(engine) as db:
            service.lock_learner(db, owner)
            record = db.get(TutoringRecord, body.tutoring_id)
            if not record or record.learner_id != owner or record.skill_id != skill_id:
                raise LearningError("not_found", "Tutoring record not found.", 404)
            if service.active_session(db, owner):
                raise LearningError("active_session", "Finish or abandon your current activity first.")
            if not tutor_service.notes(skill_id):
                raise LearningError("content_unavailable", "This topic needs published notes before continuing.")
            progress = db.get(LearningProgress, (owner, skill_id))
            if progress is None:
                progress = LearningProgress(learner_id=owner, skill_id=skill_id, phase="tutoring_complete",
                    policy_version="tutor-v2", updated_at=service.now())
                db.add(progress)
            elif progress.phase not in {"practice", "ready_for_retest", "review"}:
                progress.phase, progress.updated_at = "tutoring_complete", service.now()
        return {"skill_id": skill_id, "next": "practice"}

    @app.get("/ready")
    def ready():
        try:
            with engine.connect() as db:
                db.execute(text("SELECT 1"))
                versions = set(db.scalars(text("SELECT version_num FROM alembic_version")))
                if versions != {"b3c509d12e8f"}:
                    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "migrations_required"})
            return {"status": "ready"}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unavailable"})

    @app.get("/v1/me/account")
    def account(owner: Annotated[str, Depends(learner)]):
        return {"subject": owner, "local_development": settings.local_development,
                "content_reviewer": owner in settings.admin_subjects, "tutor_usage": budget.status(owner)}

    @app.get("/v1/me/export")
    def export_account(owner: Annotated[str, Depends(learner)]):
        return JSONResponse(content=accounts.export(owner), headers={"Content-Disposition": 'attachment; filename="mastrr-learning-data.json"', "Cache-Control": "no-store"})

    @app.delete("/v1/me/account")
    def delete_account(body: DeleteBody, owner: Annotated[str, Depends(learner)]):
        return app.state.accounts.delete(owner)

    @app.post("/v1/assignments/{assignment_id}/report", status_code=201)
    def report_question(assignment_id: str, body: ReportBody, owner: Annotated[str, Depends(learner)]):
        if len(body.message.strip()) < 10:
            raise LearningError("invalid_report", "Describe the issue in at least ten characters.", 422)
        return accounts.report(owner, assignment_id, body.message)

    def explicit_review(body):
        if body.action == "approve" and not body.confirm_reviewed:
            raise LearningError("review_required", "Confirm you personally reviewed this exact content before publishing.", 422)
        if body.action != "save" and body.document is not None:
            raise LearningError("review_required", "Save edits as a draft, then review and publish that saved version.", 422)

    @app.get("/v1/admin/questions")
    def review_questions(owner: Annotated[str, Depends(reviewer)], skill: str | None = None,
                         status: Literal["draft", "approved", "withdrawn"] | None = None,
                         offset: int = Query(default=0, ge=0), limit: int = Query(default=30, ge=1, le=100)):
        return reviews.questions(skill, status, offset, limit)

    @app.get("/v1/admin/questions/{qid}")
    def review_question(qid: str, owner: Annotated[str, Depends(reviewer)]):
        return reviews.question(qid)

    @app.post("/v1/admin/questions/{qid}")
    def decide_question(qid: str, body: ReviewBody, owner: Annotated[str, Depends(reviewer)]):
        explicit_review(body)
        try:
            return reviews.review_question(qid, owner, body.action, body.expected_checksum, body.document, body.note)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise LearningError("invalid_content", "The question structure is invalid; fix it before saving.", 422) from None

    @app.get("/v1/admin/documents/{key}")
    def review_document(key: str, owner: Annotated[str, Depends(reviewer)]):
        return reviews.document(key)

    @app.post("/v1/admin/documents/{key}")
    def decide_document(key: str, body: ReviewBody, owner: Annotated[str, Depends(reviewer)]):
        explicit_review(body)
        try:
            return reviews.review_document(key, owner, body.action, body.expected_checksum, body.document, body.note)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise LearningError("invalid_content", "The document structure is invalid; fix it before saving.", 422) from None

    @app.get("/v1/admin/reports")
    def reports(owner: Annotated[str, Depends(reviewer)]):
        return reviews.reports()

    @app.post("/v1/admin/reports/{report_id}/resolve")
    def resolve_report(report_id: str, body: ResolutionBody, owner: Annotated[str, Depends(reviewer)]):
        return reviews.resolve_report(report_id, owner, body.resolution)

    @app.post("/v1/admin/deletions/retry")
    def retry_deletions(owner: Annotated[str, Depends(reviewer)]):
        with transaction(engine) as db:
            pending = list(db.scalars(select(DeletedIdentity.subject).where(DeletedIdentity.identity_deleted.is_(False)).limit(10)))
        results = [accounts.finish_identity_deletion(subject) for subject in pending]
        return {"attempted": len(results), "completed": sum(r["identity_deleted"] for r in results)}

    @app.post("/v1/me/timed-tests", status_code=201)
    def start_timed_test(body: TimedTestBody, owner: Annotated[str, Depends(learner)]):
        return timed_practice.start(owner, body.skill_ids, body.question_count, body.minutes)

    @app.get("/v1/me/timed-tests")
    def timed_test_history(owner: Annotated[str, Depends(learner)]):
        return timed_practice.history(owner)

    @app.get("/v1/me/timed-tests/{run_id}")
    def get_timed_test(run_id: str, owner: Annotated[str, Depends(learner)]):
        return timed_practice.get(owner, run_id)

    @app.post("/v1/me/timed-tests/{run_id}/answers")
    def timed_answer(run_id: str, body: TimedAnswerBody, owner: Annotated[str, Depends(learner)]):
        return timed_practice.answer(owner, run_id, body.question_id, body.answer, body.option_id, body.dont_know)

    @app.post("/v1/me/timed-tests/{run_id}/finish")
    def finish_timed_test(run_id: str, owner: Annotated[str, Depends(learner)]):
        return timed_practice.finish(owner, run_id)

    @app.get("/v1/me/history")
    def learning_history(owner: Annotated[str, Depends(learner)]):
        from backend.models import LearningSession
        with transaction(engine) as db:
            return [{"id": s.id, "skill_id": s.skill_id, "mode": s.mode, "status": s.status,
                     "created_at": s.created_at, "policy_version": s.policy_version}
                    for s in db.scalars(select(LearningSession).where(LearningSession.learner_id == owner)
                                        .order_by(LearningSession.created_at.desc()).limit(100))]

    @app.get("/v1/me/today")
    def today(owner: Annotated[str, Depends(learner)]):
        return service.today(owner)

    @app.post("/v1/sessions", status_code=201)
    def create_session(body: SessionBody, owner: Annotated[str, Depends(learner)]):
        return service.create_session(owner, body.skill_id, body.mode, body.review_id)

    @app.get("/v1/sessions/{session_id}")
    def get_session(session_id: str, owner: Annotated[str, Depends(learner)]):
        return service.get_session(owner, session_id)

    @app.post("/v1/sessions/{session_id}/abandon")
    def abandon(session_id: str, owner: Annotated[str, Depends(learner)]):
        return service.abandon(owner, session_id)

    @app.post("/v1/assignments/{assignment_id}/submit")
    def submit(assignment_id: str, body: Submission, owner: Annotated[str, Depends(learner)],
               idempotency_key: Annotated[str, Header(min_length=1, max_length=128)]):
        return service.submit(owner, assignment_id, body.answer, body.working, idempotency_key,
                              body.duration_ms, body.dont_know, body.option_id)

    @app.post("/v1/assignments/{assignment_id}/help")
    def help(assignment_id: str, body: HelpBody, owner: Annotated[str, Depends(learner)]):
        return service.help(owner, assignment_id, body.kind)

    return app
