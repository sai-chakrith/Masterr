"""Merge learning and tutor branches; application operations and content history."""
from alembic import op
import sqlalchemy as sa

revision = "a2b8c60d741e"
down_revision = ("e913ab2f40d1", "f45b0c29d6a1")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("personal_explanations", sa.Column("learner_id", sa.String(128)))
    op.create_index("ix_personal_explanations_learner_id", "personal_explanations", ["learner_id"])
    # Old personal cache hashes cannot be reversed to identify an owner. Regenerate them.
    op.execute(sa.text("DELETE FROM personal_explanations WHERE learner_id IS NULL"))
    op.create_table("content_documents",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("status IN ('draft','approved','withdrawn')"))
    op.create_table("content_review_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("content_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("question_id", sa.String(128), sa.ForeignKey("question_versions.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=False),
        sa.Column("resolved_by", sa.String(128)),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.CheckConstraint("status IN ('open','resolved')"))
    op.create_index("ix_content_reports_learner_id", "content_reports", ["learner_id"])
    op.create_table("deleted_identities",
        sa.Column("subject", sa.String(128), primary_key=True),
        sa.Column("identity_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("usage_buckets",
        sa.Column("scope", sa.String(200), primary_key=True),
        sa.Column("period", sa.String(40), primary_key=True),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False))


def downgrade():
    for table in ("usage_buckets", "deleted_identities", "content_reports", "content_review_events", "content_documents"):
        op.drop_table(table)
    op.drop_index("ix_personal_explanations_learner_id", table_name="personal_explanations")
    op.drop_column("personal_explanations", "learner_id")
