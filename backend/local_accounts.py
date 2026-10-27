"""Username accounts for explicit loopback development; hosted auth stays Supabase."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from backend.app_models import DeletedIdentity, LocalCredential, LocalSession
from backend.db import transaction
from backend.identity_lock import lock_identity
from backend.learning import LearningError
from backend.models import Learner

COOKIE = "mastrr_session"


def now():
    return datetime.now(timezone.utc)


def check_origin(request: Request):
    from urllib.parse import urlparse
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and
            urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}):
        raise HTTPException(403, "This local account request must come from localhost.")


def digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                          maxmem=64 * 1024 * 1024).hex()


def password_hash(password):
    salt = secrets.token_hex(16)
    return "scrypt$" + salt + "$" + digest(password, salt)


def password_matches(password, encoded):
    # Missing usernames still perform the same expensive hash operation.
    _, salt, expected = (encoded or ("scrypt$" + "0" * 32 + "$" + "0" * 128)).split("$")
    return hmac.compare_digest(digest(password, salt), expected)


class LocalAccounts:
    def __init__(self, engine):
        self.engine = engine

    def authenticate(self, token):
        if not token or len(token) > 128:
            raise HTTPException(401, "Sign in to continue.")
        with transaction(self.engine) as db:
            row = db.get(LocalSession, hashlib.sha256(token.encode()).hexdigest())
            if not row or row.expires_at <= now().isoformat() or db.get(DeletedIdentity, row.learner_id):
                raise HTTPException(401, "Your session expired. Please sign in again.")
            return row.learner_id

    def sign_in(self, username, password, signup=False, remember=False):
        username = username.strip().lower()
        if signup and not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,31}", username):
            raise LearningError("invalid_username", "Use 3–32 letters, numbers, dots, hyphens or underscores.", 422)
        if signup and len(password) < 12:
            raise LearningError("weak_password", "Use a password with at least 12 characters.", 422)
        encoded = password_hash(password) if signup else None
        if not signup:
            # Do password work outside the write transaction to avoid blocking learners.
            with transaction(self.engine) as db:
                credential = db.get(LocalCredential, username)
                stored = credential.password_hash if credential else None
                subject = credential.learner_id if credential else None
            if not password_matches(password, stored):
                raise LearningError("invalid_credentials", "Username or password is incorrect.", 401)
        else:
            subject = "local-" + str(uuid4())
        token = secrets.token_urlsafe(32)
        lifetime = 7 * 86400 if remember else 12 * 3600
        try:
            with transaction(self.engine) as db:
                lock_identity(db, subject)
                if db.get(DeletedIdentity, subject):
                    raise LearningError("invalid_credentials", "Username or password is incorrect.", 401)
                if signup:
                    db.add(Learner(id=subject))
                    db.flush()
                    db.add(LocalCredential(username=username, learner_id=subject, password_hash=encoded))
                elif not db.scalar(select(LocalCredential).where(
                        LocalCredential.username == username, LocalCredential.learner_id == subject)):
                    raise LearningError("invalid_credentials", "Username or password is incorrect.", 401)
                db.execute(delete(LocalSession).where(LocalSession.expires_at <= now().isoformat()))
                db.add(LocalSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                    learner_id=subject, expires_at=(now() + timedelta(seconds=lifetime)).isoformat()))
        except IntegrityError:
            raise LearningError("username_unavailable", "That username is unavailable. Try another.", 409) from None
        return token, lifetime, username

    def sign_out(self, token):
        if token:
            with transaction(self.engine) as db:
                db.execute(delete(LocalSession).where(LocalSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
