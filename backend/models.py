"""Persistent records for the first deterministic learning loop."""
from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Learner(Base):
    __tablename__ = "learners"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)


class Question(Base):
    __tablename__ = "question_versions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    skill_id: Mapped[str] = mapped_column(String(128), index=True)
    family_id: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    facet: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    checksum: Mapped[str] = mapped_column(String(64))
    difficulty_level: Mapped[int | None] = mapped_column(Integer)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sub_topic: Mapped[str | None] = mapped_column(String(128))
    # Private snapshot: never serialize this object into student responses.
    snapshot: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("item_id", "version"),
        CheckConstraint("difficulty_level BETWEEN 1 AND 5"),
        CheckConstraint("status IN ('draft','approved','withdrawn')"),
        CheckConstraint("purpose IN ('diagnostic','practice','verification','review')"),
    )


class LearningSession(Base):
    __tablename__ = "learning_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    skill_id: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(32))
    policy_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40))
    # Review being fulfilled; a separate FK below avoids a circular schema dependency.
    review_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (CheckConstraint("mode IN ('diagnostic','practice','verification','review')"),)


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    solution_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("session_id", "position"),)


class Exposure(Base):
    __tablename__ = "exposure_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    family_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40))
    __table_args__ = (Index("ix_exposure_learner_family", "learner_id", "family_id"),)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    predicted_probability: Mapped[float | None] = mapped_column(Float)
    scoring_version: Mapped[str] = mapped_column(String(32), default="current", server_default="current")
    raw_answer: Mapped[str] = mapped_column(Text)
    normalized_answer: Mapped[int] = mapped_column(Integer)
    working: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    assistance: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("learner_id", "idempotency_key"),
        CheckConstraint("duration_ms >= 0"),
        CheckConstraint("predicted_probability BETWEEN 0 AND 1"),
        CheckConstraint("scoring_version IN ('current','new')"),
    )


class Evidence(Base):
    __tablename__ = "evidence_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence_events.id"))
    skill_id: Mapped[str] = mapped_column(String(128))
    occasion: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32))
    completed_at: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        UniqueConstraint("evidence_id", "occasion"),
        Index("ix_review_due", "learner_id", "status", "due_at"),
    )


class TopicScoringConfig(Base):
    """Per-learner/topic assignment; defaults preserve the current learning policy."""
    __tablename__ = "topic_scoring_configs"
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scoring_version: Mapped[str] = mapped_column(String(32), default="current", server_default="current")
    __table_args__ = (CheckConstraint("scoring_version IN ('current','new')"),)


class MasteryEstimate(Base):
    """Track 1 owns rating updates; no historical ratings are fabricated."""
    __tablename__ = "mastery_estimates"
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    answer_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    recent_changes: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (CheckConstraint("answer_count >= 0"),)
