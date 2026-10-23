import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.auth import Settings, make_identity
from backend.content import import_questions
from backend.db import Base, make_engine, transaction
from backend.numbers.bank import load_questions


@pytest.fixture
def client(tmp_path):
    engine = make_engine("sqlite:///" + str(tmp_path / "api.db"))
    Base.metadata.create_all(engine)
    settings = Settings(database_url="", local_development=True, local_token="t" * 32)
    app = create_app(engine, settings)
    with transaction(engine) as db:
        question = copy.deepcopy(load_questions()[3])
        question.update(review_status="approved", review={"reviewer": "test-fixture", "date": "test-only"})
        import_questions(db, [question])
    with TestClient(app) as client:
        yield client
    engine.dispose()


def auth():
    return {"Authorization": "Bearer " + "t" * 32}


def test_identity_required_and_client_cannot_choose_owner(client):
    assert client.get("/v1/me/today").status_code == 401
    assert client.get("/v1/me/today", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/v1/sessions", headers=auth(), json={"learner_id": "victim"}).status_code == 422


def test_api_session_submission_resume_and_grading(client):
    created = client.post("/v1/sessions", headers=auth(), json={})
    assert created.status_code == 201
    sid = created.json()["session_id"]
    question = client.get("/v1/sessions/" + sid, headers=auth()).json()["question"]
    headers = {**auth(), "Idempotency-Key": "submit-1"}
    path = "/v1/assignments/" + question["assignment_id"] + "/submit"
    response = client.post(path, headers=headers, json={"answer": "4", "working": "both 2 and 3"})
    assert response.status_code == 200 and response.json()["correct"]
    assert client.post(path, headers=headers, json={"answer": "4", "working": "both 2 and 3"}).json() == response.json()
    assert client.get("/v1/me/today", headers=auth()).json()["evidence"]
    assert client.get("/health").json()["ai_enabled"] is False


def test_api_typed_exhaustion_and_validation(client):
    response = client.post("/v1/sessions", headers=auth(), json={"mode": "verification"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_coverage"
    assert client.post("/v1/sessions", headers=auth(), json={"mode": "invented"}).status_code == 422


def test_supabase_jwt_checks_signature_claims_and_expiry(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = Mock()
    client.get_signing_key_from_jwt.return_value.key = key.public_key()
    monkeypatch.setattr(jwt, "PyJWKClient", lambda url: client)
    identify = make_identity(Settings(database_url="", supabase_url="https://example.supabase.co"))
    claims = {"sub": "student-1", "role": "authenticated", "iss": "https://example.supabase.co/auth/v1",
              "aud": "authenticated", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    def token(data):
        return "Bearer " + jwt.encode(data, key, algorithm="RS256")
    assert identify(token(claims)) == "student-1"
    for patch in ({"aud": "other"}, {"iss": "https://wrong"}, {"exp": 0}, {"sub": ""}, {"role": "anon"}):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            identify(token({**claims, **patch}))
        assert error.value.status_code == 401
