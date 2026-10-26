"""Reviewer-only publication with immutable versions and optimistic concurrency."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app_models import ContentDocument, ContentReport, ReviewEvent
from backend.content import import_questions
from backend.curriculum import curriculum_digest, load_curriculum, validate_curriculum
from backend.db import transaction
from backend.exam_profiles import load_exam_profiles, validate_exam_profiles
from backend.learning import LearningError
from backend.models import Misconception, Question
from backend.numbers.bank import load_misconceptions, validate_bank
from backend.publication import checksum, document_row, load_document

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def latest_questions():
    return select(Question.item_id, func.max(Question.version).label("version")).group_by(Question.item_id).subquery()


class ReviewService:
    def __init__(self, engine):
        self.engine = engine

    def event(self, db, target, actor, action, sha, note):
        db.add(ReviewEvent(id=str(uuid4()), target=target, actor=actor, action=action,
                           checksum=sha, note=note, created_at=now()))

    def questions(self, skill=None, status=None, offset=0, limit=30):
        latest = latest_questions()
        with transaction(self.engine) as db:
            query = select(Question).join(latest, (Question.item_id == latest.c.item_id) & (Question.version == latest.c.version))
            if skill:
                query = query.where(Question.skill_id == skill)
            if status:
                query = query.where(Question.status == status)
            count = db.scalar(select(func.count()).select_from(query.subquery()))
            rows = db.scalars(query.order_by(Question.item_id).offset(offset).limit(limit))
            return {"total": count, "items": [{"id": q.id, "skill_id": q.skill_id, "status": q.status,
                    "hidden": q.hidden, "purpose": q.purpose, "prompt": q.snapshot["prompt"], "checksum": q.checksum} for q in rows]}

    def question(self, qid):
        with transaction(self.engine) as db:
            q = db.get(Question, qid)
            if not q:
                raise LearningError("not_found", "Question not found.", 404)
            return {"id": q.id, "checksum": q.checksum, "document": q.snapshot}

    def review_question(self, qid, actor, action, expected, payload=None, note=""):
        try:
            with transaction(self.engine) as db:
                old = db.get(Question, qid)
                if not old:
                    raise LearningError("not_found", "Question not found.", 404)
                latest = db.scalar(select(Question).where(Question.item_id == old.item_id)
                                   .order_by(Question.version.desc()).limit(1).with_for_update())
                if latest.id != qid or latest.checksum != expected:
                    raise LearningError("stale_content", "This question changed. Reload it before reviewing.")
                item = deepcopy(payload if action == "save" and payload is not None else old.snapshot)
                if item.get("id") != old.item_id or item.get("skill_id") != old.skill_id:
                    raise LearningError("invalid_content", "Editing cannot change the item ID or topic.", 422)
                item["version"] = old.version + 1
                item["review_status"] = {"save": "draft", "approve": "approved", "withdraw": "withdrawn"}[action]
                item.pop("review", None)
                if action != "save":
                    item["review"] = {"reviewer": actor, "date": now()[:10]}
                concepts = load_document(self.engine, "misconceptions", lambda: {"misconceptions": load_misconceptions()})["misconceptions"]
                problems = validate_bank([item], concepts)
                if problems:
                    raise LearningError("invalid_content", "; ".join(problems), 422)
                import_questions(db, [item], concepts)
                new = db.get(Question, item["id"] + "@" + str(item["version"]))
                self.event(db, "question:" + old.item_id, actor, action, new.checksum, note)
                return {"id": new.id, "checksum": new.checksum, "document": new.snapshot}
        except IntegrityError:
            raise LearningError("stale_content", "Another reviewer updated this item. Reload it.") from None

    def seed_document(self, key):
        if key == "curriculum":
            return load_curriculum()
        if key == "exam-profiles":
            return load_exam_profiles()
        if key == "misconceptions":
            return {"status": "draft", "misconceptions": load_misconceptions()}
        if key.startswith("notes:") and key[6:] in {s["id"] for s in load_curriculum()["skills"]}:
            path = ROOT / "reference" / "tutor-notes-v2" / (key[6:] + ".md")
            return {"status": "draft", "text": path.read_text(encoding="utf-8") if path.is_file() else ""}
        raise LearningError("not_found", "Unknown content document.", 404)

    def document(self, key):
        seed = self.seed_document(key)
        with transaction(self.engine) as db:
            row = document_row(db, key)
            published = document_row(db, key, published=True)
            return {"key": key, "version": row.version if row else 0,
                    "status": row.status if row else seed.get("status", "draft"),
                    "published": bool(published and published.status == "approved"),
                    "checksum": row.checksum if row else checksum(seed),
                    "document": row.payload if row else seed}

    def review_document(self, key, actor, action, expected, payload=None, note=""):
        seed = self.seed_document(key)
        try:
            with transaction(self.engine) as db:
                row = document_row(db, key)
                old = row.payload if row else seed
                if (row.checksum if row else checksum(seed)) != expected:
                    raise LearningError("stale_content", "This document changed. Reload it before reviewing.")
                document = deepcopy(payload if action == "save" and payload is not None else old)
                status = {"save": "draft", "approve": "approved", "withdraw": "withdrawn"}[action]
                document["status"] = "approved" if action == "approve" else "draft"
                document.pop("review", None)
                document.pop("approval_checksum", None)
                review = {"reviewer": actor, "date": now()[:10]}
                if action == "approve":
                    document["review"] = review
                problems = []
                if key == "curriculum":
                    if {s["id"] for s in document.get("skills", [])} != {s["id"] for s in seed["skills"]}:
                        problems.append("Topic IDs must match the deployed curriculum; add new topics through a code/content release.")
                    if action == "approve":
                        document["approval_checksum"] = curriculum_digest(document)
                    problems += validate_curriculum(document)
                elif key == "exam-profiles":
                    for profile in document.get("profiles", []):
                        profile.pop("review", None)
                        if action == "approve":
                            profile["review"] = review
                    problems += validate_exam_profiles(document)
                elif key == "misconceptions":
                    for concept in document.get("misconceptions", []):
                        concept["review_status"] = "approved" if action == "approve" else "draft"
                        concept.pop("review", None)
                        if action == "approve":
                            concept["review"] = review
                        previous = db.get(Misconception, concept["id"])
                        if previous and (previous.description != concept["description"] or previous.short_fix != concept["short_fix"]):
                            problems.append("Changed misconception text needs a new ID to preserve historical feedback.")
                    problems += validate_bank([], document.get("misconceptions", []))
                elif not isinstance(document.get("text"), str) or not document["text"].strip() or len(document["text"]) > 24000:
                    problems.append("Notes require nonempty text of at most 24,000 characters.")
                elif action == "approve":
                    document["text"] = document["text"].replace("Status: draft. Original material for human review.",
                                                               "Status: approved for tutoring after review.")
                if problems:
                    raise LearningError("invalid_content", "; ".join(problems), 422)
                sha = checksum(document)
                db.add(ContentDocument(key=key, version=row.version + 1 if row else 1,
                    status=status, payload=document, checksum=sha, actor=actor, created_at=now()))
                if key == "misconceptions" and action == "approve":
                    for item in document["misconceptions"]:
                        if not db.get(Misconception, item["id"]):
                            db.add(Misconception(id=item["id"], skill_id=item["skill_id"],
                                description=item["description"], short_fix=item["short_fix"]))
                self.event(db, key, actor, action, sha, note)
        except IntegrityError:
            raise LearningError("stale_content", "Another reviewer updated this document. Reload it.") from None
        return self.document(key)

    def reports(self):
        with transaction(self.engine) as db:
            return [{"id": r.id, "question_id": r.question_id, "message": r.message,
                     "status": r.status, "resolution": r.resolution, "created_at": r.created_at}
                    for r in db.scalars(select(ContentReport).order_by(ContentReport.created_at.desc()).limit(100))]

    def resolve_report(self, report_id, actor, resolution):
        with transaction(self.engine) as db:
            row = db.get(ContentReport, report_id)
            if not row:
                raise LearningError("not_found", "Report not found.", 404)
            row.status, row.resolution, row.resolved_by = "resolved", resolution, actor
            self.event(db, "report:" + report_id, actor, "resolve", checksum(resolution), resolution)
        return {"status": "resolved"}
