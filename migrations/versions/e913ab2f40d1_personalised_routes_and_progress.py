"""learner goals, practice progress, and recommendation events

Revision ID: e913ab2f40d1
Revises: b7d41e0c2a15
"""
from alembic import op
import sqlalchemy as sa


revision = "e913ab2f40d1"
down_revision = "b7d41e0c2a15"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learner_goals",
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("curriculum_id", sa.String(128), nullable=False),
        sa.Column("curriculum_version", sa.String(64), nullable=False),
        sa.Column("target_skill_ids", sa.JSON(), nullable=False),
        sa.Column("exam_profile_id", sa.String(128)),
        sa.Column("exam_profile_version", sa.String(64)),
        sa.Column("exam_profile_snapshot", sa.JSON()),
        sa.Column("exam_date", sa.String(10)),
        sa.Column("timezone", sa.String(64), server_default="Asia/Kolkata", nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "learning_progress",
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("skill_id", sa.String(128), primary_key=True),
        sa.Column("phase", sa.String(40), server_default="none", nullable=False),
        sa.Column("practice_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("best_probability", sa.Float()),
        sa.Column("no_progress_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recent_probabilities", sa.JSON(), nullable=False),
        sa.Column("stuck", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.CheckConstraint("phase IN ('none','diagnostic','tutoring','tutoring_complete','practice','ready_for_retest','stuck','review')", name="ck_learning_progress_phase"),
        sa.CheckConstraint("practice_count >= 0", name="ck_learning_progress_count"),
        sa.CheckConstraint("no_progress_count >= 0", name="ck_learning_progress_no_progress"),
        sa.CheckConstraint("best_probability IS NULL OR best_probability BETWEEN 0 AND 1", name="ck_learning_progress_probability"),
    )
    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("action_kind", sa.String(40), nullable=False),
        sa.Column("skill_id", sa.String(128)),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("state_fingerprint", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), server_default="shown", nullable=False),
        sa.Column("shown_at", sa.String(40), nullable=False),
        sa.Column("followed_at", sa.String(40)),
        sa.Column("dismissed_at", sa.String(40)),
        sa.CheckConstraint("status IN ('shown','followed','dismissed','expired')", name="ck_recommendation_status"),
    )
    op.create_index("ix_recommendation_learner_shown", "recommendation_events", ["learner_id", "shown_at"])
    op.create_index("ix_recommendation_events_learner_id", "recommendation_events", ["learner_id"])
    op.create_table(
        "topic_practice_configs",
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), primary_key=True),
        sa.Column("skill_id", sa.String(128), primary_key=True),
        sa.Column("strategy", sa.String(24), server_default="personalised", nullable=False),
        sa.CheckConstraint("strategy IN ('personalised','fixed')", name="ck_topic_practice_strategy"),
    )
    op.create_table(
        "misconceptions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("skill_id", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("short_fix", sa.Text(), nullable=False),
    )
    op.create_index("ix_misconceptions_skill_id", "misconceptions", ["skill_id"])
    op.create_table(
        "question_options",
        sa.Column("question_id", sa.String(128), sa.ForeignKey("question_versions.id"), primary_key=True),
        sa.Column("option_id", sa.String(128), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("misconception_id", sa.String(128), sa.ForeignKey("misconceptions.id")),
        sa.UniqueConstraint("question_id", "position"),
        sa.CheckConstraint("position >= 0", name="ck_question_option_position"),
    )
    op.add_column("attempts", sa.Column("selected_option_id", sa.String(128)))
    op.add_column("attempts", sa.Column("misconception_id", sa.String(128)))


def downgrade():
    op.drop_column("attempts", "misconception_id")
    op.drop_column("attempts", "selected_option_id")
    op.drop_table("question_options")
    op.drop_index("ix_misconceptions_skill_id", table_name="misconceptions")
    op.drop_table("misconceptions")
    op.drop_table("topic_practice_configs")
    op.drop_index("ix_recommendation_events_learner_id", table_name="recommendation_events")
    op.drop_index("ix_recommendation_learner_shown", table_name="recommendation_events")
    op.drop_table("recommendation_events")
    op.drop_table("learning_progress")
    op.drop_table("learner_goals")
