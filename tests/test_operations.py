import json
import sqlite3
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.auth import Settings
from backend.db import make_engine
from scripts.operations import backup_sqlite, doctor


def test_backup_restores_schema_and_rows_without_overwriting(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "source.db")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    with sqlite3.connect(tmp_path / "source.db") as db:
        db.execute("INSERT INTO learners (id) VALUES ('private-synthetic-learner')")
    assert doctor(engine)["migrations_current"]
    result = backup_sqlite(engine, tmp_path / "backup.db")
    assert result["restore_verified"]
    with sqlite3.connect(tmp_path / "backup.db") as db:
        assert db.execute("SELECT id FROM learners").fetchone()[0] == "private-synthetic-learner"
    with pytest.raises(ValueError, match="never overwritten"):
        backup_sqlite(engine, tmp_path / "source.db")
    with pytest.raises(ValueError, match="never overwritten"):
        backup_sqlite(engine, tmp_path / "backup.db")
    engine.dispose()


def test_ready_body_limit_and_safe_request_logs(tmp_path, monkeypatch, caplog):
    url = "sqlite:///" + str(tmp_path / "ready.db")
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    app = create_app(engine, Settings(database_url="", local_development=True, local_token="t" * 32))
    with TestClient(app) as client, caplog.at_level("INFO", logger="mastrr.requests"):
        response = client.get("/ready?secret=do-not-log-me")
        assert response.status_code == 200 and response.headers["x-request-id"]
        assert "do-not-log-me" not in caplog.text
        response = client.post("/v1/sessions", content="x" * 1_048_577)
        assert response.status_code == 413 and response.headers["cache-control"] == "no-store"
    engine.dispose()
