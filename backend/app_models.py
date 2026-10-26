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
