"""Shared-database quotas, private exports, deletion and learner content reports."""
import hashlib
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app_models import ContentReport, DeletedIdentity, UsageBucket
from backend.db import Base, transaction
from backend.learning import LearningError
from backend.identity_lock import lock_identity
from backend.models import Assignment, Learner, LearningSession


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def owner_scope(owner):
    return hashlib.sha256(owner.encode()).hexdigest()


class BudgetService:
    def __init__(self, engine):
        self.engine = engine
        self.daily_calls = int(os.environ.get("MASTRR_TUTOR_DAILY_CALLS", "60"))
        self.daily_tokens = int(os.environ.get("MASTRR_TUTOR_DAILY_TOKEN_BUDGET", "120000"))
        self.global_tokens = int(os.environ.get("MASTRR_TUTOR_GLOBAL_TOKEN_BUDGET", "1000000"))
        self.api_per_minute = int(os.environ.get("MASTRR_API_REQUESTS_PER_MINUTE", "120"))
        if min(self.daily_calls, self.daily_tokens, self.global_tokens, self.api_per_minute) < 1:
            raise ValueError("Application request and tutor limits must be positive.")

    def _row(self, db, scope, period):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert = sqlite_insert if self.engine.dialect.name == "sqlite" else pg_insert
        db.execute(insert(UsageBucket).values(scope=scope, period=period, calls=0, reserved_tokens=0)
                   .on_conflict_do_nothing(index_elements=["scope", "period"]))
        return db.scalar(select(UsageBucket).where(UsageBucket.scope == scope, UsageBucket.period == period).with_for_update())

    def rate_limit(self, owner, limit=None):
        with transaction(self.engine) as db:
            bucket = self._row(db, "api:" + owner_scope(owner), utcnow()[:16])
            if bucket.calls >= (limit if limit is not None else self.api_per_minute):
                raise LearningError("rate_limit", "Too many requests. Please wait a minute.", 429)
            bucket.calls += 1

    def reserve(self, owner, tokens):
        # Stable lock order prevents cross-worker deadlocks; reservations are conservative.
        with transaction(self.engine) as db:
            shared = self._row(db, "tutor:global", utcnow()[:10])
            personal = self._row(db, "tutor:" + owner_scope(owner), utcnow()[:10])
            if (personal.calls >= self.daily_calls or personal.reserved_tokens + tokens > self.daily_tokens
                    or shared.reserved_tokens + tokens > self.global_tokens):
                return False
            for row in (shared, personal):
                row.calls += 1
                row.reserved_tokens += tokens
        return True

    def status(self, owner):
        with Session(self.engine) as db:
            row = db.get(UsageBucket, ("tutor:" + owner_scope(owner), utcnow()[:10]))
            return {"calls": row.calls if row else 0, "reserved_completion_tokens": row.reserved_tokens if row else 0,
                    "daily_call_limit": self.daily_calls, "daily_completion_token_limit": self.daily_tokens,
                    "period": utcnow()[:10], "timezone": "UTC"}


def delete_hosted_identity(settings, subject):
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        raise RuntimeError("Identity deletion is not configured")
    from urllib.parse import quote
    request = Request(settings.supabase_url + "/auth/v1/admin/users/" + quote(subject, safe=""),
                      method="DELETE", headers={"Authorization": "Bearer " + key, "apikey": key})
    try:
        with urlopen(request, timeout=20) as response:
            response.read()
    except HTTPError as error:
        if error.code != 404:
            raise


class AccountService:
    def __init__(self, engine, settings, delete_identity=delete_hosted_identity):
        self.engine, self.settings, self.delete_identity = engine, settings, delete_identity

    def export(self, owner):
        with transaction(self.engine) as db:
            db.scalar(select(Learner).where(Learner.id == owner).with_for_update())
            from backend.mock_state import active_test
            if active_test(db, owner):
                raise LearningError("active_session", "Finish your timed practice before exporting data.")
            sessions = list(db.scalars(select(LearningSession).where(LearningSession.learner_id == owner)))
            if any(s.status in {"active", "assisted"} for s in sessions):
                raise LearningError("active_session", "Finish or abandon your current activity before exporting data.")
            session_ids = [s.id for s in sessions]
            result = {}
            for table in Base.metadata.sorted_tables:
                if table.name in {"local_credentials", "local_sessions"}:
                    continue  # Password hashes and session verifiers never belong in exports.
                if "learner_id" in table.c:
                    rows = db.execute(select(table).where(table.c.learner_id == owner)).mappings().all()
                    result[table.name] = [dict(row) for row in rows]
            result["assignments"] = [dict(r) for r in db.execute(select(Assignment.__table__).where(
                Assignment.session_id.in_(session_ids))).mappings()]
            for row in result.get("attempts", []):
                if row.get("source") == "validation":
                    for field in ("correct", "response", "predicted_probability"):
                        row.pop(field, None)
            return {"format_version": 1, "exported_at": utcnow(), "learner_id": owner, "data": result}

    def delete(self, owner):
        if not self.settings.local_development and not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
            raise LearningError("deletion_unavailable", "Account deletion needs server configuration. Contact support.", 503)
        with transaction(self.engine) as db:
            lock_identity(db, owner)
            record = db.get(Learner, owner)
            if record is not None:
                # Locking the learner serialises deletion with allocation and submission.
                db.scalar(select(Learner).where(Learner.id == owner).with_for_update())
            sessions = list(db.scalars(select(LearningSession.id).where(LearningSession.learner_id == owner)))
            # Children before parents; publication/reviewer audit is deliberately retained.
            for table in reversed(Base.metadata.sorted_tables):
                if "learner_id" in table.c:
                    db.execute(delete(table).where(table.c.learner_id == owner))
                elif table.name == "assignments":
                    db.execute(delete(table).where(table.c.session_id.in_(sessions)))
            db.execute(delete(Learner).where(Learner.id == owner))
            for scope in ("api:" + owner_scope(owner), "tutor:" + owner_scope(owner)):
                db.execute(delete(UsageBucket).where(UsageBucket.scope == scope))
            tombstone = db.get(DeletedIdentity, owner)
            if not tombstone:
                db.add(DeletedIdentity(subject=owner, identity_deleted=self.settings.local_development, created_at=utcnow()))
        return self.finish_identity_deletion(owner)

    def finish_identity_deletion(self, owner):
        done = self.settings.local_development
        if not done:
            try:
                self.delete_identity(self.settings, owner)
                done = True
            except Exception:
                pass  # No provider errors or keys in logs; operator can retry the tombstone.
        with transaction(self.engine) as db:
            row = db.get(DeletedIdentity, owner)
            if row:
                row.identity_deleted = done
        return {"data_deleted": True, "identity_deleted": done,
                "message": "Account deleted." if done else "Learning data deleted; sign-in disabled. Identity deletion is queued for retry."}

    def report(self, owner, assignment_id, message):
        with transaction(self.engine) as db:
            assignment = db.get(Assignment, assignment_id)
            session = db.get(LearningSession, assignment.session_id) if assignment else None
            if not session or session.learner_id != owner:
                raise LearningError("not_found", "Question not found.", 404)
            from backend.models import Exposure
            if not db.scalar(select(Exposure.id).where(Exposure.assignment_id == assignment_id, Exposure.learner_id == owner)):
                raise LearningError("not_found", "Open this question before reporting it.", 404)
            row = ContentReport(id=str(uuid4()), learner_id=owner, question_id=assignment.question_id,
                                message=message.strip(), status="open", resolution="", created_at=utcnow())
            db.add(row)
            return {"id": row.id, "status": "open"}
