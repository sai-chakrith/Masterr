"""Explicitly labelled sample fixtures restricted to a separate local demo database."""
import copy
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from backend.content import import_questions
from backend.curriculum import curriculum_digest, load_curriculum, validate_curriculum
from backend.db import make_engine, transaction
from backend.numbers.bank import load_questions, load_misconceptions
from backend.app_models import ContentDocument
from backend.publication import checksum

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / ".demo"
MARKER = "MASTRR_ISOLATED_DEMO_NOT_HUMAN_REVIEWED"


def assert_demo_database(engine):
    if os.environ.get("MASTRR_ENV") == "production" or engine.dialect.name != "sqlite":
        raise ValueError("Demo mode is restricted to local SQLite, never production.")
    path = Path(engine.url.database or "").resolve()
    if not path.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError("Demo mode requires an isolated database under .demo/.")
    try:
        marker = json.loads((path.parent / "demo-only.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Demo database marker is missing or invalid.") from None
    if marker != {"kind": MARKER, "database": path.name}:
        raise ValueError("Demo database marker does not match this database.")


def prepare_demo(topic="divisibility", seed_mistakes=False):
    catalog = copy.deepcopy(load_curriculum())
    if topic not in {s["id"] for s in catalog["skills"]}:
        raise ValueError("Choose a topic in the current curriculum.")
    DEMO_ROOT.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="recording-", dir=DEMO_ROOT)).resolve()
    if not folder.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError("Demo directory escaped its intended root.")
    database = folder / "demo.db"
    (folder / "demo-only.json").write_text(json.dumps({"kind": MARKER, "database": database.name}), encoding="utf-8")
    url = "sqlite:///" + str(database)
    # Alembic reads the explicit URL; never inherit a real DATABASE_URL for preparation.
    previous = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = url
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
    review = {"reviewer": MARKER, "date": datetime.now(timezone.utc).date().isoformat()}
    questions, concepts = copy.deepcopy(load_questions()), copy.deepcopy(load_misconceptions())
    for item in questions:
        item.update(review_status="approved", review=review, demo_sample=True)
        item["provenance"] += " ISOLATED DEMONSTRATION SAMPLE: not human-reviewed or learner evidence."
    for concept in concepts:
        concept.update(review_status="approved", review=review)
    catalog.update(status="approved", review=review)
    catalog["approval_checksum"] = curriculum_digest(catalog)
    problems = validate_curriculum(catalog)
    if problems:
        raise ValueError("The sample curriculum is invalid; fix the source drafts before preparing a demo.")
    engine = make_engine(url)
    try:
        with transaction(engine) as db:
            import_questions(db, questions, concepts)
            payloads = {"curriculum": catalog, "misconceptions": {"status": "approved", "misconceptions": concepts, "review": review}}
            for skill in catalog["skills"]:
                path = ROOT / "reference" / "tutor-notes-v2" / (skill["id"] + ".md")
                payloads["notes:" + skill["id"]] = {"status": "approved", "review": review,
                    "text": "Demonstration sample; not human-reviewed.\n\n" + path.read_text(encoding="utf-8")}
            for key, payload in payloads.items():
                db.add(ContentDocument(key=key, version=1, status="approved", payload=payload,
                    checksum=checksum(payload), actor=MARKER, created_at=datetime.now(timezone.utc).isoformat()))
        from backend.learning import LearningService
        from backend.personalisation import PersonalisationService
        service = LearningService(engine)
        service.register("local-developer")
        for skill in catalog["skills"]:
            service.set_scoring_version("local-developer", skill["id"], "new")
        PersonalisationService(engine, service).set_goal("local-developer", [topic])
        if seed_mistakes:
            sid = service.create_session("local-developer", topic, "diagnostic")["session_id"]
            for _ in range(12):
                view = service.get_session("local-developer", sid)
                if view["status"] == "completed":
                    break
                assignment = view["question"]["assignment_id"]
                result = service.submit("local-developer", assignment, "", "", assignment, dont_know=True)
                if result["session_complete"]:
                    break
    finally:
        engine.dispose()
    token_path = folder / "api-token"
    descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(secrets.token_urlsafe(32))
    manifest = {"database_url": url, "folder": str(folder), "token_file": str(token_path), "topic": topic,
                "seeded_sample_mistakes": seed_mistakes, "kind": MARKER}
    (DEMO_ROOT / "latest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
