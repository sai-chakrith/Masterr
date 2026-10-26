"""CI-only PostgreSQL smoke and public-role isolation checks."""
import os
from sqlalchemy import text
from backend.db import make_engine


def main():
    if os.environ.get("MASTRR_POSTGRES_TEST") != "1":
        raise SystemExit("Run only against an isolated test database with MASTRR_POSTGRES_TEST=1.")
    engine = make_engine(os.environ["DATABASE_URL"])
    if engine.dialect.name != "postgresql":
        raise SystemExit("This verification requires PostgreSQL.")
    with engine.connect() as db:
        transaction = db.begin()
        try:
            secured = db.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid = 'question_versions'::regclass"))
            assert secured is True
            for role in ("anon", "authenticated"):
                db.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role}; END IF; END $$"))
                db.execute(text(f"GRANT SELECT ON question_versions, learners TO {role}"))
                db.execute(text(f"SET LOCAL ROLE {role}"))
                assert db.scalar(text("SELECT count(*) FROM question_versions")) == 0
                assert db.scalar(text("SELECT count(*) FROM learners")) == 0
                db.execute(text("RESET ROLE"))
            print("PostgreSQL RLS denies browser-role reads, including when SELECT was granted in the test.")
        finally:
            transaction.rollback()
    engine.dispose()


if __name__ == "__main__":
    main()
