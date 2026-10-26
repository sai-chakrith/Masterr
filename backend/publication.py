"""Database publications override seed files; editing drafts never publishes them."""
from copy import deepcopy
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app_models import ContentDocument


def checksum(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def document_row(db, key, *, published=False):
    query = select(ContentDocument).where(ContentDocument.key == key)
    if published:
        query = query.where(ContentDocument.status != "draft")
    return db.scalar(query.order_by(ContentDocument.version.desc()).limit(1))


def load_document(engine, key, fallback):
    with Session(engine) as db:
        row = document_row(db, key, published=True)
        if row:
            if row.checksum != checksum(row.payload):
                raise ValueError("Published content checksum mismatch")
            if row.status == "withdrawn":
                content = deepcopy(row.payload)
                content["status"] = "draft"
                return content
            return deepcopy(row.payload)
    return fallback()


def topic_notes(engine, topic):
    from backend.retrieval import get_topic_notes
    from backend.curriculum import load_curriculum
    with Session(engine) as db:
        row = document_row(db, "notes:" + topic, published=True)
        if row:
            return row.payload.get("text", "") if row.status == "approved" and row.checksum == checksum(row.payload) else ""
    # Reviewed file-based notes remain supported.
    text = get_topic_notes(topic)
    if text:
        return text
    curriculum = load_document(engine, "curriculum", load_curriculum)
    if curriculum.get("status") == "approved":
        return next((s.get("lesson", "") for s in curriculum["skills"] if s["id"] == topic), "")
    return ""
