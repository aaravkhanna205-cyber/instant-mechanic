"""Phase 7: HR manager and hiring manager roles; notification links and email delivery.

Revision ID: 0011_phase7_enterprise
Revises: 0010_phase6_job_analytics
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_phase7_enterprise'
down_revision = '0010_phase6_job_analytics'
branch_labels = None
depends_on = None

ROLE_CHECK = 'ck_organization_memberships_allowed_role'


def _roles(roles: str) -> None:
    op.execute(f'ALTER TABLE organization_memberships DROP CONSTRAINT IF EXISTS {ROLE_CHECK}')
    op.execute(f'ALTER TABLE organization_memberships ADD CONSTRAINT {ROLE_CHECK} CHECK (role IN ({roles}))')


def upgrade():
    _roles("'owner','admin','hr_manager','hiring_manager','recruiter','interviewer','candidate'")
    # Migration 0001 builds tables from the current models, so a brand-new database already has
    # these columns. Only add what is missing (keeps fresh installs and upgrades both working).
    have = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('notifications')}
    columns = [
        sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('link', sa.String(300)),
        sa.Column('email_status', sa.String(20)),
        sa.Column('emailed_at', sa.DateTime(timezone=True)),
        sa.Column('email_error', sa.String(300)),
    ]
    for column in columns:
        if column.name not in have:
            op.add_column('notifications', column)
    op.execute('CREATE INDEX IF NOT EXISTS ix_notifications_organization_id ON notifications (organization_id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_notifications_email_status ON notifications (email_status)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications (user_id, read_at)')

def downgrade():
    for index in ('ix_notifications_user_unread', 'ix_notifications_email_status', 'ix_notifications_organization_id'):
        op.execute(f'DROP INDEX IF EXISTS {index}')
    for column in ('email_error', 'emailed_at', 'email_status', 'link', 'organization_id'):
        op.drop_column('notifications', column)
    # Members with the new roles keep full access as organization admins.
    op.execute("UPDATE organization_memberships SET role = 'admin' WHERE role IN ('hr_manager','hiring_manager')")
    _roles("'owner','admin','recruiter','interviewer','candidate'")
