"""Application operations, publication history and account tombstones."""
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.db import Base


class ContentDocument(Base):
    __tablename__ = "content_documents"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("status IN ('draft','approved','withdrawn')"),)


class ReviewEvent(Base):
    __tablename__ = "content_review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target: Mapped[str] = mapped_column(String(200))
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(16))
    checksum: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))


class ContentReport(Base):
    __tablename__ = "content_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("status IN ('open','resolved')"),)


class DeletedIdentity(Base):
    __tablename__ = "deleted_identities"
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    identity_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(String(40))


class UsageBucket(Base):
    __tablename__ = "usage_buckets"
    scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    period: Mapped[str] = mapped_column(String(40), primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)


class LocalCredential(Base):
    __tablename__ = "local_credentials"
    username: Mapped[str] = mapped_column(String(32), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))


class LocalSession(Base):
    __tablename__ = "local_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    expires_at: Mapped[str] = mapped_column(String(40))


class TimedTest(Base):
    __tablename__ = "timed_tests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    skill_ids: Mapped[list] = mapped_column(JSON)
    question_ids: Mapped[list] = mapped_column(JSON)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))
    deadline: Mapped[str] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))


class TestExposure(Base):
    __tablename__ = "test_exposures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("timed_tests.id"))
    family_id: Mapped[str] = mapped_column(String(128))
