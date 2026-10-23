"""Import original content without inventing review or modifying published versions."""
import hashlib
import json

from sqlalchemy import select

from backend.models import Question
from backend.numbers.bank import validate_bank

FACETS = ("basic", "combined", "constraints")


def import_questions(db, questions):
    errors = validate_bank(questions)
    if errors:
        raise ValueError("; ".join(errors))
    imported = 0
    for question in questions:
        version = question.get("version", 1)
        if type(version) is not int or version < 1:
            raise ValueError("Question version must be a positive integer")
        qid = f"{question['id']}@{version}"
        digest = hashlib.sha256(json.dumps(question, sort_keys=True).encode()).hexdigest()
        current = db.get(Question, qid)
        if current:
            if current.checksum != digest:
                raise ValueError(f"{qid} changed: create a new version")
            continue
        facet = question.get("facet", "unclassified")
        if facet not in (*FACETS, "unclassified"):
            raise ValueError("Unknown coverage facet")
        if question["review_status"] == "approved":
            review = question.get("review", {})
            if not all(isinstance(review.get(k), str) and review[k].strip() for k in ("reviewer", "date")):
                raise ValueError("Approval requires reviewer and date")
        db.add(Question(
            id=qid, item_id=question["id"], version=version,
            skill_id=question["skill_id"], family_id=question["family_id"],
            purpose=question["purpose"], facet=facet,
            status=question["review_status"], checksum=digest, snapshot=question,
        ))
        imported += 1
    db.flush()
    return imported


def available_questions(db, skill_id, purpose):
    return list(db.scalars(select(Question).where(
        Question.skill_id == skill_id, Question.purpose == purpose,
        Question.status == "approved",
    ).order_by(Question.item_id, Question.version.desc())))
