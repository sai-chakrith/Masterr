"""Local username credentials and revocable sessions."""
from alembic import op
import sqlalchemy as sa

revision = "c6e1f892a470"
down_revision = "b3c509d12e8f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("local_credentials",
        sa.Column("username", sa.String(32), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False))
    op.create_table("local_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False))
    op.create_index("ix_local_sessions_learner_id", "local_sessions", ["learner_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in ("local_credentials", "local_sessions"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC'))
            for role in ("anon", "authenticated"):
                op.execute(sa.text(f'''DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        REVOKE ALL ON TABLE "{table}" FROM {role};
                    END IF;
                END $$'''))


def downgrade():
    op.drop_table("local_sessions")
    op.drop_table("local_credentials")
