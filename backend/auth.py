"""Verify server-controlled local credentials or Supabase asymmetric JWTs."""
from dataclasses import dataclass
import hmac
import os

import jwt
from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Settings:
    database_url: str
    supabase_url: str = ""
    local_token: str = ""
    local_development: bool = False

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/local.db"),
            supabase_url=os.environ.get("SUPABASE_URL", "").rstrip("/"),
            local_token=os.environ.get("LOCAL_API_TOKEN", ""),
            local_development=os.environ.get("LOCAL_DEVELOPMENT") == "1",
        )


def make_identity(settings):
    if settings.local_development:
        if len(settings.local_token) < 32:
            raise ValueError("Local development requires LOCAL_API_TOKEN of at least 32 characters")
        jwks = None
    else:
        if not settings.supabase_url.startswith("https://"):
            raise ValueError("Configure SUPABASE_URL or explicit local development")
        jwks = jwt.PyJWKClient(settings.supabase_url + "/auth/v1/.well-known/jwks.json")

    def identity(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        token = authorization[7:]
        if settings.local_development:
            if not hmac.compare_digest(token.encode(), settings.local_token.encode()):
                raise HTTPException(status_code=401, detail="Invalid identity")
            return "local-developer"
        try:
            key = jwks.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token, key, algorithms=["ES256", "RS256"], audience="authenticated",
                issuer=settings.supabase_url + "/auth/v1",
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
            if payload.get("role") != "authenticated":
                raise ValueError("User token required")
            subject = payload["sub"]
            if not isinstance(subject, str) or not subject or len(subject) > 128:
                raise ValueError("Invalid subject")
            return subject
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid identity") from None
    return identity
