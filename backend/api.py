"""First learning-loop API. Run on loopback only when using local development."""
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import Settings, make_identity
from backend.db import make_engine
from backend.learning import LearningError, LearningService
from backend.tutor import TutorService
from backend.personalisation import PersonalisationError, PersonalisationService
from backend.curriculum import load_curriculum
from backend.exam_profiles import approved_profiles, load_exam_profiles


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


def create_app(engine=None, settings=None):
    settings = settings or Settings.from_env()
    engine = engine or make_engine(settings.database_url)
    service = LearningService(engine)
    tutor_service = TutorService(engine)
    personalisation = PersonalisationService(engine, service)
    app = FastAPI(title="Mastrr learning API", version="0.1.0")
    app.state.service = service
    app.state.tutor = tutor_service
    app.state.personalisation = personalisation
    authenticate = make_identity(settings)

    def learner(subject: Annotated[str, Depends(authenticate)]):
        service.register(subject)
        return subject

    @app.exception_handler(LearningError)
    def domain_error(request: Request, error: LearningError):
        return JSONResponse(status_code=error.status,
                            content={"error": {"code": error.code, "message": error.message}})

    @app.exception_handler(PersonalisationError)
    def personalisation_error(request: Request, error: PersonalisationError):
        return JSONResponse(status_code=error.status,
                            content={"error": {"code": error.code, "message": error.message}})

    @app.get("/v1/curriculum")
    def curriculum(owner: Annotated[str, Depends(learner)]):
        document = load_curriculum()
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
                for profile in approved_profiles(load_exam_profiles())
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

    @app.post("/v1/me/tutor/{skill_id}")
    def tutor(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return app.state.tutor.tutor(owner, skill_id)

    @app.get("/v1/me/tutor/topics")
    def tutor_topics(owner: Annotated[str, Depends(learner)]):
        from backend.numbers.bank import load_curriculum as tutor_curriculum
        return [{"id": s["id"], "title": s["title"]} for s in tutor_curriculum()["skills"]]

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
