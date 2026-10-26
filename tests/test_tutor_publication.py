import hashlib
import json
import sys

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from backend.db import make_engine
from backend.retrieval import get_topic_notes
from scripts import tutor_notes


def test_publish_requires_explicit_review_and_binds_file_hash(tmp_path, monkeypatch):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "divisibility.md").write_text("Status: draft. Original material for human review.\n\nMethod.", encoding="utf-8")
    monkeypatch.setattr(tutor_notes, "ROOT", tmp_path)
    monkeypatch.setattr(tutor_notes, "DRAFTS", drafts)
    monkeypatch.setattr(sys, "argv", ["tutor_notes", "publish", "divisibility"])
    with pytest.raises(SystemExit) as error:
        tutor_notes.main()
    assert error.value.code != 0
    assert not (tmp_path / "knowledge").exists()
    monkeypatch.setattr(sys, "argv", ["tutor_notes", "publish", "divisibility",
                                     "--reviewer", "synthetic-test-only", "--review-date", "2026-10-20", "--confirm-reviewed"])
    tutor_notes.main()
    path = tmp_path / "knowledge" / "notes" / "divisibility.md"
    metadata = json.loads(path.with_suffix(".review.json").read_text())
    assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert "approved" in get_topic_notes("divisibility", path.parent)
    monkeypatch.setattr("backend.retrieval.load_curriculum", lambda: {"status": "draft", "skills": []})
    path.write_text("Edited without review.")
    assert get_topic_notes("divisibility", path.parent) == ""


def test_upgrade_keeps_existing_learner_and_is_repeatable(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "old.db")
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "b7d41e0c2a15")
    engine = make_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO learners (id) VALUES ('existing-learner')"))
    engine.dispose()
    command.upgrade(config, "heads")
    command.upgrade(config, "heads")
    engine = make_engine(url)
    with engine.connect() as db:
        assert db.scalar(text("SELECT id FROM learners")) == "existing-learner"
        assert {"topic_lessons", "personal_explanations", "tutoring_content"} <= set(inspect(db).get_table_names())
    engine.dispose()
