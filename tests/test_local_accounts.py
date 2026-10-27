"""Real local account requests, isolated learners and revocable cookie sessions."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.api import create_app
from backend.auth import Settings
from backend.app_models import LocalCredential, LocalSession
from backend.db import Base, make_engine, transaction

PASSWORD = "Synthetic-password-2026"


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    # Keep minute-bucket assertions deterministic if the suite crosses a minute.
    monkeypatch.setattr("backend.operations.utcnow", lambda: "2026-10-27T10:00:00+00:00")
    engine = make_engine("sqlite:///" + str(tmp_path / "accounts.db"))
    Base.metadata.create_all(engine)
    app = create_app(engine, Settings(database_url="", local_development=True))
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def signup(client, username="learner_one", **extra):
    return client.post("/v1/auth/signup", json={"username": username, "password": PASSWORD, **extra})


def test_signup_login_logout_and_password_storage(accounts):
    client, engine = accounts
    response = signup(client, remember=True)
    assert response.status_code == 201
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=604800" in cookie
    assert "token" not in response.json()
    assert not client.get("/v1/me/account").json()["content_reviewer"]
    token = client.cookies.get("mastrr_session")
    with transaction(engine) as db:
        credential = db.get(LocalCredential, "learner_one")
        assert credential.password_hash.startswith("scrypt$") and PASSWORD not in credential.password_hash
        assert token not in db.scalar(select(LocalSession)).token_hash
    assert client.post("/v1/auth/logout").status_code == 200
    assert client.get("/v1/me/account").status_code == 401
    client.cookies.set("mastrr_session", token)
    assert client.get("/v1/me/account").status_code == 401
    client.cookies.clear()
    assert client.post("/v1/auth/login", json={"username": "LEARNER_ONE", "password": PASSWORD}).status_code == 200
    assert client.get("/v1/me/account").status_code == 200


def test_separate_progress_private_export_and_deleted_account(accounts):
    client, _ = accounts
    assert signup(client).status_code == 201
    first = client.get("/v1/me/account").json()["subject"]
    assert client.put("/v1/me/goal", json={"target_skill_ids": ["divisibility"]}).status_code == 200
    exported = client.get("/v1/me/export").json()["data"]
    assert "local_credentials" not in exported and "local_sessions" not in exported
    assert signup(client, "learner_two").status_code == 201
    assert client.get("/v1/me/account").json()["subject"] != first
    assert client.get("/v1/me/goal").json() is None
    assert client.request("DELETE", "/v1/me/account", json={"confirmation": "DELETE"}).status_code == 200
    assert client.get("/v1/me/account").status_code == 401
    assert client.post("/v1/auth/login", json={"username": "learner_two", "password": PASSWORD}).status_code == 401


def test_invalid_credentials_validation_expiry_and_throttling(accounts):
    client, engine = accounts
    assert signup(client).status_code == 201
    assert signup(client, "LEARNER_ONE").status_code == 409
    for username in ("learner_one", "not_an_account"):
        response = client.post("/v1/auth/login", json={"username": username, "password": "wrong"})
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Username or password is incorrect."
    with transaction(engine) as db:
        for row in db.scalars(select(LocalSession)):
            row.expires_at = "2000-01-01T00:00:00+00:00"
    assert client.get("/v1/me/account").status_code == 401
    assert client.post("/v1/auth/signup", json={"username": "bad name", "password": PASSWORD}).status_code == 422
    assert client.post("/v1/auth/signup", json={"username": "okay", "password": "short"}).status_code == 422
    for _ in range(11):
        response = client.post("/v1/auth/login", json={"username": "blocked", "password": "wrong"})
    assert response.status_code == 429


def test_cross_site_and_hosted_mode_reject_local_accounts(accounts):
    client, engine = accounts
    assert client.post("/v1/auth/signup", json={"username": "learner_one", "password": PASSWORD},
                       headers={"Origin": "https://another-site.example"}).status_code == 403
    hosted = create_app(engine, Settings(database_url="", supabase_url="https://example.supabase.co"))
    with TestClient(hosted) as remote:
        assert signup(remote).status_code == 404
