"""mastery scoring v2: answer source, I-don't-know flag, session version and stage

Revision ID: b7d41e0c2a15
Revises: ca64a7954ed7
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7d41e0c2a15'
down_revision = 'ca64a7954ed7'
branch_labels = None
depends_on = None

SESSION_CHECKS = (
    sa.CheckConstraint("mode IN ('diagnostic','practice','verification','review')", name='ck_session_mode'),
)
ATTEMPT_CHECKS = (
    sa.CheckConstraint('duration_ms >= 0', name='ck_attempt_duration'),
    sa.CheckConstraint('predicted_probability BETWEEN 0 AND 1', name='ck_attempt_prediction'),
    sa.CheckConstraint("scoring_version IN ('current','new')", name='ck_attempt_scoring_version'),
)


def upgrade():
    with op.batch_alter_table('learning_sessions', schema=None, table_args=SESSION_CHECKS) as batch_op:
        batch_op.add_column(sa.Column('scoring_version', sa.String(length=32), server_default='current', nullable=False))
        batch_op.add_column(sa.Column('stage', sa.String(length=16), nullable=True))
        batch_op.create_check_constraint('ck_session_scoring_version', "scoring_version IN ('current','new')")
        batch_op.create_check_constraint('ck_session_stage', "stage IN ('pre','post','delayed')")

    with op.batch_alter_table('attempts', schema=None, table_args=ATTEMPT_CHECKS) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=16), server_default='practice', nullable=False))
        batch_op.add_column(sa.Column('dont_know', sa.Boolean(), server_default='0', nullable=False))
        batch_op.create_check_constraint(
            'ck_attempt_source',
            "source IN ('diagnostic','practice','verification','review','retest','validation')")

    # Existing answers keep their meaning: derive source from the session, and the
    # Track 2 literal skip marker becomes the explicit flag.
    op.execute("""
        UPDATE attempts SET source = COALESCE((
            SELECT CASE WHEN s.policy_version = 'topic-retest-v1' THEN 'retest' ELSE s.mode END
            FROM assignments a JOIN learning_sessions s ON s.id = a.session_id
            WHERE a.id = attempts.assignment_id), 'practice')
    """)
    op.execute("UPDATE attempts SET dont_know = (raw_answer = 'I don''t know' AND correct = false)")


def downgrade():
    with op.batch_alter_table('attempts', schema=None, table_args=ATTEMPT_CHECKS) as batch_op:
        batch_op.drop_constraint('ck_attempt_source', type_='check')
        batch_op.drop_column('dont_know')
        batch_op.drop_column('source')

    with op.batch_alter_table('learning_sessions', schema=None, table_args=SESSION_CHECKS) as batch_op:
        batch_op.drop_constraint('ck_session_stage', type_='check')
        batch_op.drop_constraint('ck_session_scoring_version', type_='check')
        batch_op.drop_column('stage')
        batch_op.drop_column('scoring_version')
