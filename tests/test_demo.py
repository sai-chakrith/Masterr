import hashlib
from pathlib import Path
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend import demo
from backend.api import create_app
from backend.auth import Settings
from backend.db import make_engine, transaction
from backend.local_env import load_local_env
from backend.models import Attempt
from backend.tutor import TutorService, TutorSettings


def test_local_env_never_overwrites_process_or_executes_shell(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text('GROQ_API_KEY="synthetic-not-a-real-key"\nMASTRR_LLM_MODEL=model-a\nPATH=do-not-apply\n', encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "existing-test-value")
    monkeypatch.delenv("MASTRR_LLM_MODEL", raising=False)
    old_path = __import__("os").environ.get("PATH")
    loaded = load_local_env(file)
    import os
    assert os.environ["GROQ_API_KEY"] == "existing-test-value"
    assert os.environ["MASTRR_LLM_MODEL"] == "model-a" and os.environ.get("PATH") == old_path
    assert loaded == {"MASTRR_LLM_MODEL"}


def test_env_parser_errors_never_include_the_value(tmp_path):
    file = tmp_path / ".env"
    file.write_text('GROQ_API_KEY="synthetic-sensitive-value\n')
    with pytest.raises(ValueError) as caught:
        load_local_env(file)
    assert "synthetic-sensitive-value" not in str(caught.value)


def test_demo_isolated_seeded_and_visible_without_modifying_source(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    monkeypatch.setattr(demo, "DEMO_ROOT", root)
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("MASTRR_DEMO", "1")
    monkeypatch.setenv("MASTRR_ENV", "development")
    source = demo.ROOT / "content/numbers/questions.json"
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = demo.prepare_demo("divisibility", seed_mistakes=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    assert Path(manifest["token_file"]).is_relative_to(root)
    engine = make_engine(manifest["database_url"])
    demo.assert_demo_database(engine)
    with transaction(engine) as db:
        assert db.scalar(select(func.count()).select_from(Attempt)) >= 8
    token = Path(manifest["token_file"]).read_text()
    app = create_app(engine, Settings(database_url="", local_development=True, local_token=token))
    with TestClient(app) as client:
        assert client.get("/runtime").json() == {"demo": True, "ai_configured": False}
        result = client.post("/v1/me/tutor/divisibility", headers={"Authorization": "Bearer " + token})
        assert result.status_code == 200 and len(result.json()["selected_question_ids"]) == 3
        assert result.json()["generated_by"] == "fallback"
    engine.dispose()


def test_demo_mode_refuses_normal_database_and_production(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTRR_DEMO", "1")
    engine = make_engine("sqlite:///" + str(tmp_path / "normal.db"))
    with pytest.raises(ValueError, match="isolated"):
        create_app(engine, Settings(database_url="", local_development=True, local_token="t" * 32))
    assert not (tmp_path / "normal.db").exists()
    monkeypatch.setenv("MASTRR_ENV", "production")
    with pytest.raises(ValueError, match="Production"):
        create_app(engine, Settings(database_url="", local_development=True, local_token="t" * 32))
    engine.dispose()


def test_provider_http_errors_are_sanitized(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "unused.db"))
    def rejected(*args):
        raise HTTPError("https://api.groq.com", 401, "synthetic-sensitive-value", {}, None)
    tutor = TutorService(engine, TutorSettings(api_key="synthetic-not-real"), completion=rejected)
    usage = []
    assert tutor._call_llm("system", {}, "lesson", usage) is None
    assert usage[0]["http_status"] == 401
    assert "synthetic-sensitive-value" not in str(usage)
    engine.dispose()
