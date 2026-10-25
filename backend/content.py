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
        level = question.get("difficulty_level")
        if level is not None and (type(level) is not int or not 1 <= level <= 5):
            raise ValueError("Difficulty level must be an integer from 1 to 5")
        hidden = question.get("hidden", False)
        if type(hidden) is not bool:
            raise ValueError("Hidden must be a boolean")
        sub_topic = question.get("sub_topic")
        if sub_topic is not None and (not isinstance(sub_topic, str) or len(sub_topic) > 128):
            raise ValueError("Subtopic must be text of at most 128 characters")
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
            difficulty_level=level, hidden=hidden, sub_topic=sub_topic,
        ))
        imported += 1
    db.flush()
    return imported


def available_questions(db, skill_id, purpose):
    return list(db.scalars(select(Question).where(
        Question.skill_id == skill_id, Question.purpose == purpose,
        Question.status == "approved", Question.hidden.is_(False),
    ).order_by(Question.item_id, Question.version.desc())))
