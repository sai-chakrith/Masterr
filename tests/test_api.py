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


def test_track2_routes_require_identity_and_report_bank_exhaustion(client):
    assert client.get("/v1/me/gaps").status_code == 401
    assert client.post("/v1/topics/divisibility/retest").status_code == 401
    gaps = client.get("/v1/me/gaps", headers=auth())
    assert gaps.status_code == 200
    assert all(g["status"] == "unassessed" for g in gaps.json())
    response = client.post("/v1/topics/divisibility/retest", headers=auth())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_coverage"
    assert client.post("/v1/topics/unknown/retest", headers=auth()).status_code == 422


def test_skip_api_validation_and_storage(client):
    created = client.post("/v1/sessions", headers=auth(), json={}).json()
    item = client.get("/v1/sessions/" + created["session_id"], headers=auth()).json()["question"]
    path = "/v1/assignments/" + item["assignment_id"] + "/submit"
    headers = {**auth(), "Idempotency-Key": "skip"}
    assert client.post(path, headers=headers, json={"answer": "4", "dont_know": True}).status_code == 422
    response = client.post(path, headers=headers, json={"dont_know": True})
    assert response.status_code == 200 and response.json()["correct"] is False
    assert client.post(path, headers=headers, json={"dont_know": True}).json() == response.json()


def test_validation_route_requires_identity_and_reports_missing_forms(client):
    assert client.post("/v1/topics/divisibility/validation").status_code == 401
    response = client.post("/v1/topics/divisibility/validation", headers=auth())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_coverage"
    assert client.post("/v1/topics/unknown/validation", headers=auth()).status_code == 422


def test_gaps_payload_carries_dashboard_fields(client):
    row = client.get("/v1/me/gaps", headers=auth()).json()[0]
    assert {"title", "scoring_version", "score", "answer_count", "mastery_bar", "score_withheld"} <= set(row)


def test_goal_route_api_returns_content_gating_and_pace(client):
    response = client.put("/v1/me/goal", headers=auth(), json={
        "target_skill_ids": ["hcf-lcm"], "exam_date": "2026-12-01", "timezone": "Asia/Kolkata",
    })
    assert response.status_code == 200
    assert response.json()["route_skill_ids"] == [
        "integer-properties", "divisibility", "primes-factors", "hcf-lcm",
    ]
    roadmap = client.get("/v1/me/roadmap", headers=auth())
    assert roadmap.status_code == 200
    assert roadmap.json()["weekly_pace"]["remaining_topics"] == 4
    assert all(node["available"] is False for node in roadmap.json()["nodes"])
    suggestion = client.get("/v1/me/next-action", headers=auth()).json()
    assert suggestion["actions"] == []
    assert suggestion["availability"] == "no_reviewed_content_for_next_step"


def test_unreviewed_exam_profiles_are_rejected_explicitly(client):
    response = client.put("/v1/me/goal", headers=auth(), json={
        "target_skill_ids": ["divisibility"], "exam_profile_id": "bank-po",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "profile_unavailable"
