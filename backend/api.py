"""First learning-loop API. Run on loopback only when using local development."""
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.auth import Settings, make_identity
from backend.db import make_engine
from backend.learning import LearningError, LearningService


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionBody(StrictBody):
    skill_id: str = Field(default="divisibility", max_length=128)
    mode: Literal["diagnostic", "practice", "verification", "review"] = "practice"
    review_id: str | None = Field(default=None, max_length=36)


class Submission(StrictBody):
    answer: str = Field(default="", max_length=32)
    dont_know: bool = Field(default=False, strict=True)
    working: str = Field(default="", max_length=2000)
    duration_ms: int | None = Field(default=None, ge=0, le=86400000, strict=True)


class HelpBody(StrictBody):
    kind: Literal["hint", "solution"]


def create_app(engine=None, settings=None):
    settings = settings or Settings.from_env()
    engine = engine or make_engine(settings.database_url)
    service = LearningService(engine)
    app = FastAPI(title="Mastrr learning API", version="0.1.0")
    app.state.service = service
    authenticate = make_identity(settings)

    def learner(subject: Annotated[str, Depends(authenticate)]):
        service.register(subject)
        return subject

    @app.exception_handler(LearningError)
    def domain_error(request: Request, error: LearningError):
        return JSONResponse(status_code=error.status,
                            content={"error": {"code": error.code, "message": error.message}})

    @app.get("/v1/me/gaps")
    def gaps(owner: Annotated[str, Depends(learner)]):
        return service.gaps(owner)

    @app.post("/v1/topics/{skill_id}/retest", status_code=201)
    def retest(skill_id: str, owner: Annotated[str, Depends(learner)]):
        return service.create_session(owner, skill_id, "verification", retest=True)

    @app.get("/v1/sessions/{session_id}/borderline-review")
    def borderline_review(session_id: str, owner: Annotated[str, Depends(learner)]):
        return service.borderline_review(owner, session_id)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0", "ai_enabled": False}

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
        return service.submit(owner, assignment_id, body.answer, body.working, idempotency_key, body.duration_ms, body.dont_know)

    @app.post("/v1/assignments/{assignment_id}/help")
    def help(assignment_id: str, body: HelpBody, owner: Annotated[str, Depends(learner)]):
        return service.help(owner, assignment_id, body.kind)

    return app
