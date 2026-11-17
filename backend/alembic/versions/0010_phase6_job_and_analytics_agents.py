"""Phase 6: job description and analytics runs are not tied to one application.

Revision ID: 0010_phase6_job_analytics
Revises: 0009_phase6_interview_summary
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_phase6_job_analytics'
down_revision = '0009_phase6_interview_summary'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('phase6_workflow_runs', 'application_id', existing_type=sa.Uuid(), nullable=True)


def downgrade():
    op.execute('DELETE FROM phase6_workflow_runs WHERE application_id IS NULL')
    op.alter_column('phase6_workflow_runs', 'application_id', existing_type=sa.Uuid(), nullable=False)
