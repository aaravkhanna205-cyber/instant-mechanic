"""Phase 6 workflow runs (checkpoints for the Resume Review workflow).

Revision ID: 0008_phase6_workflow_runs
Revises: 0007_phase6_email_tracking
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_phase6_workflow_runs'
down_revision = '0007_phase6_email_tracking'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('phase6_workflow_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow', sa.String(40), nullable=False),
        sa.Column('application_id', sa.Uuid(), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='running'),
        sa.Column('step', sa.String(40)),
        sa.Column('state', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text()),
        sa.Column('started_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('reviewed_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('review_decision', sa.String(24)),
        sa.Column('review_note', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('running','waiting_resume','waiting_review','completed','failed','cancelled')",
                           name='ck_p6_run_status'))
    op.create_index('ix_phase6_workflow_runs_organization_id', 'phase6_workflow_runs', ['organization_id'])
    op.create_index('ix_phase6_workflow_runs_application_id', 'phase6_workflow_runs', ['application_id'])
    op.create_index('ix_p6_runs_org_status', 'phase6_workflow_runs', ['organization_id', 'status'])


def downgrade():
    op.drop_table('phase6_workflow_runs')
