"""Topic lesson and personal explanation caches, tutoring audit records.

Revision ID: f45b0c29d6a1
Revises: b7d41e0c2a15
"""
from alembic import op
import sqlalchemy as sa

revision = "f45b0c29d6a1"
down_revision = "b7d41e0c2a15"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("topic_lessons", "personal_explanations"):
        op.create_table(table,
                        sa.Column("cache_key", sa.String(64), primary_key=True),
                        sa.Column("payload", sa.JSON(), nullable=False))
    op.create_table("tutoring_content",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
                    sa.Column("skill_id", sa.String(128), nullable=False),
                    sa.Column("model", sa.String(128), nullable=False),
                    sa.Column("prompt_version", sa.String(64), nullable=False),
                    sa.Column("notes_hash", sa.String(64), nullable=False),
                    sa.Column("created_at", sa.String(40), nullable=False),
                    sa.Column("content", sa.Text(), nullable=False),
                    sa.Column("parts", sa.JSON(), nullable=False),
                    sa.Column("usage", sa.JSON(), nullable=False))
    op.create_index("ix_tutoring_content_learner_id", "tutoring_content", ["learner_id"])


def downgrade():
    op.drop_index("ix_tutoring_content_learner_id", table_name="tutoring_content")
    op.drop_table("tutoring_content")
    op.drop_table("personal_explanations")
    op.drop_table("topic_lessons")
