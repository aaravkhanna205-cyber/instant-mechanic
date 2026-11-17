"""Phase 8: server error log for System health.

Revision ID: 0012_phase8_server_errors
Revises: 0011_phase7_enterprise
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_phase8_server_errors'
down_revision = '0011_phase7_enterprise'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('server_errors'):  # a brand-new database may already have it (0001)
        return
    op.create_table(
        'server_errors',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('path', sa.String(200), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False),
        sa.Column('error_type', sa.String(120), nullable=False),
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_server_errors_created_at ON server_errors (created_at)')


def downgrade():
    op.execute('DROP TABLE IF EXISTS server_errors')
