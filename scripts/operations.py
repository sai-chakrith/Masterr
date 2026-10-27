"""Readiness checks, safe SQLite backup/restore verification and housekeeping."""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import delete, select, text
from backend.app_models import DeletedIdentity, UsageBucket
from backend.auth import Settings
from backend.db import make_engine, transaction
from backend.operations import AccountService
from backend.review import ReviewService
from backend.publication import load_document
from backend.curriculum import load_curriculum


def doctor(engine):
    result = {"database": False, "migrations_current": False, "published_curriculum": False,
              "approved_questions": 0, "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
              "hosted_auth_configured": bool(os.environ.get("SUPABASE_URL")),
              "reviewers_configured": bool(os.environ.get("MASTRR_ADMIN_SUBJECTS"))}
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1")); result["database"] = True
            result["migrations_current"] = set(db.scalars(text("SELECT version_num FROM alembic_version"))) == {"c6e1f892a470"}
        result["published_curriculum"] = load_document(engine, "curriculum", load_curriculum).get("status") == "approved"
        result["approved_questions"] = ReviewService(engine).questions(status="approved", limit=1)["total"]
    except Exception:
        result["reason"] = "Database is unavailable or needs migrations. No credentials are printed."
    return result


def backup_sqlite(engine, destination):
    if engine.dialect.name != "sqlite" or not engine.url.database or engine.url.database == ":memory:":
        raise ValueError("This command backs up on-disk SQLite only. Use pg_dump for PostgreSQL.")
    source = Path(engine.url.database).resolve()
    target = Path(destination).resolve()
    if target == source or target.exists():
        raise ValueError("Choose a new backup filename; existing databases are never overwritten.")
    if not source.is_file():
        raise ValueError("Source database does not exist.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as original, sqlite3.connect(target) as backup:
        original.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup integrity check failed.")
    # Independently restore to memory and check schema and referential integrity.
    with sqlite3.connect(target) as backup, sqlite3.connect(":memory:") as restored:
        backup.backup(restored)
        if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or restored.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Restore verification failed.")
        version = restored.execute("SELECT version_num FROM alembic_version").fetchall()
    return {"backup": str(target), "restore_verified": True, "schema_versions": [r[0] for r in version]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "backup-sqlite", "prune", "retry-deletions"])
    parser.add_argument("--out")
    args = parser.parse_args()
    engine = make_engine(os.environ.get("DATABASE_URL", "sqlite:///./data/local.db"))
    try:
        if args.command == "doctor":
            result = doctor(engine); print(json.dumps(result, indent=2))
            if not result["database"] or not result["migrations_current"]:
                raise SystemExit(1)
        elif args.command == "backup-sqlite":
            if not args.out:
                parser.error("--out must name a new backup file outside the live database.")
            print(json.dumps(backup_sqlite(engine, args.out), indent=2))
        elif args.command == "prune":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
            with transaction(engine) as db:
                result = db.execute(delete(UsageBucket).where(UsageBucket.period < cutoff))
                print(json.dumps({"expired_usage_buckets_removed": result.rowcount}))
        else:
            with transaction(engine) as db:
                pending = list(db.scalars(select(DeletedIdentity.subject).where(DeletedIdentity.identity_deleted.is_(False))))
            accounts = AccountService(engine, Settings.from_env())
            results = [accounts.finish_identity_deletion(owner) for owner in pending]
            print(json.dumps({"attempted": len(results), "completed": sum(r["identity_deleted"] for r in results)}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
