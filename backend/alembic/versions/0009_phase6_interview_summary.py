"""Phase 6 workflow 3: allow the 'waiting_interview' run status.

Revision ID: 0009_phase6_interview_summary
Revises: 0008_phase6_workflow_runs
"""
from alembic import op

revision = '0009_phase6_interview_summary'
down_revision = '0008_phase6_workflow_runs'
branch_labels = None
depends_on = None

NAME = 'ck_phase6_workflow_runs_ck_p6_run_status'


def _replace(statuses: str) -> None:
    op.execute(f'ALTER TABLE phase6_workflow_runs DROP CONSTRAINT IF EXISTS {NAME}')
    op.execute('ALTER TABLE phase6_workflow_runs DROP CONSTRAINT IF EXISTS ck_p6_run_status')
    op.execute(f'ALTER TABLE phase6_workflow_runs ADD CONSTRAINT {NAME} CHECK (status IN ({statuses}))')


def upgrade():
    _replace("'running','waiting_resume','waiting_interview','waiting_review','completed','failed','cancelled'")


def downgrade():
    op.execute("UPDATE phase6_workflow_runs SET status = 'failed' WHERE status = 'waiting_interview'")
    _replace("'running','waiting_resume','waiting_review','completed','failed','cancelled'")
