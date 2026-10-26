"""Independent timed mixed-topic practice; never used as mastery evidence."""
from alembic import op
import sqlalchemy as sa
revision = "b3c509d12e8f"
down_revision = "a2b8c60d741e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("timed_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("skill_ids", sa.JSON(), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("deadline", sa.String(40), nullable=False),
        sa.Column("finished_at", sa.String(40)))
    op.create_index("ix_timed_tests_learner_id", "timed_tests", ["learner_id"])
    op.create_table("test_exposures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("timed_tests.id"), nullable=False),
        sa.Column("family_id", sa.String(128), nullable=False))
    op.create_index("ix_test_exposures_learner_id", "test_exposures", ["learner_id"])
    if op.get_bind().dialect.name == "postgresql":
        # Browser Supabase clients use Auth only. Application tables must not be
        # accessible through PostgREST's public anon/authenticated roles.
        tables = ("alembic_version", "assignments", "attempts", "content_documents", "content_reports",
            "content_review_events", "deleted_identities", "evidence_events", "exposure_events", "gap_states",
            "learner_goals", "learners", "learning_progress", "learning_sessions", "mastery_estimates",
            "misconceptions", "personal_explanations", "question_options", "question_versions",
            "recommendation_events", "reviews", "test_exposures", "timed_tests", "topic_lessons",
            "topic_practice_configs", "topic_scoring_configs", "tutoring_content", "usage_buckets")
        for table in tables:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'REVOKE ALL ON TABLE "{table}" FROM PUBLIC'))
            for role in ("anon", "authenticated"):
                op.execute(sa.text(f'''DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        REVOKE ALL ON TABLE "{table}" FROM {role};
                    END IF;
                END $$'''))


def downgrade():
    # Do not restore public database access when rolling back this feature.
    op.drop_table("test_exposures")
    op.drop_table("timed_tests")
