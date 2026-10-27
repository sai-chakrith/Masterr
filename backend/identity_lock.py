"""Serialize identity lifecycle even when its learner row does not exist."""
import hashlib
from sqlalchemy import text


def lock_identity(db, subject):
    # SQLite transactions already use BEGIN IMMEDIATE. PostgreSQL needs a
    # transaction-scoped lock that survives deletion of the learner row.
    if db.bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(subject.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
