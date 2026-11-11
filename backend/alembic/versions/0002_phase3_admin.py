"""Additional administration tables for the Phase 3 roadmap.

Revision ID: 0002_phase3_admin
Revises: 0001_fresh_schema
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_phase3_admin'
down_revision = '0001_fresh_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('app_settings', sa.Column('key', sa.String(120), primary_key=True), sa.Column('value', sa.JSON(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('import_batches', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False), sa.Column('created_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')), sa.Column('filename', sa.String(240), nullable=False), sa.Column('kind', sa.String(32), nullable=False), sa.Column('status', sa.String(32), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('import_rows', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('batch_id', sa.Uuid(), sa.ForeignKey('import_batches.id', ondelete='CASCADE'), nullable=False), sa.Column('row_number', sa.Integer(), nullable=False), sa.Column('job_id', sa.Uuid(), sa.ForeignKey('jobs.id', ondelete='SET NULL')), sa.Column('error', sa.Text()), sa.Column('data', sa.JSON(), nullable=False))
    op.create_index('ix_import_rows_batch_id', 'import_rows', ['batch_id'])
    op.create_table('password_reset_requests', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('token_digest', sa.String(64), unique=True, nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), sa.Column('used_at', sa.DateTime(timezone=True)))
    op.create_table('data_deletion_requests', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('status', sa.String(32), nullable=False, server_default='pending'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('feature_flags', sa.Column('key', sa.String(120), primary_key=True), sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    for name in ['feature_flags','data_deletion_requests','password_reset_requests','import_rows','import_batches','app_settings']:
        op.drop_table(name)
