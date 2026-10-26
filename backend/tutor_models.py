"""Tutor caches and per-visit provenance; no assessment grades live here."""
from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class TopicLesson(Base):
    __tablename__ = "topic_lessons"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PersonalExplanation(Base):
    __tablename__ = "personal_explanations"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class TutoringRecord(Base):
    __tablename__ = "tutoring_content"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    skill_id: Mapped[str] = mapped_column(String(128))
    model: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    notes_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    parts: Mapped[dict] = mapped_column(JSON)
    usage: Mapped[list] = mapped_column(JSON)
