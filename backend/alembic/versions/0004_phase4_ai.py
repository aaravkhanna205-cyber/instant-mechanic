"""Phase 4 advisory resume processing and vector excerpts.

Revision ID: 0004_phase4_ai
Revises: 0003_phase3_completion
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
revision='0004_phase4_ai'
down_revision='0003_phase3_completion'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table('phase4_documents',
      sa.Column('id',sa.Uuid(),primary_key=True),
      sa.Column('candidate_id',sa.Uuid(),sa.ForeignKey('candidate_profiles.id',ondelete='CASCADE'),nullable=False),
      sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
      sa.Column('filename',sa.String(255),nullable=False),
      sa.Column('file_ext',sa.String(5),nullable=False),
      sa.Column('sha256',sa.String(64),nullable=False),
      sa.Column('size_bytes',sa.Integer(),nullable=False),
      sa.Column('consented',sa.Boolean(),server_default=sa.text('false'),nullable=False),
      sa.Column('status',sa.String(24),server_default='queued',nullable=False),
      sa.Column('skills',sa.JSON(),nullable=False,server_default='[]'),
      sa.Column('error',sa.String(250)),
      sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.Column('processed_at',sa.DateTime(timezone=True)),
      sa.CheckConstraint("status IN ('queued','ready','failed')",name='ck_p4_document_status'),
      sa.CheckConstraint('size_bytes > 0',name='ck_p4_document_size'))
    op.create_index('ix_p4_docs_candidate','phase4_documents',['candidate_id'])
    op.create_table('phase4_chunks',
      sa.Column('id',sa.BigInteger(),sa.Identity(),primary_key=True),
      sa.Column('document_id',sa.Uuid(),sa.ForeignKey('phase4_documents.id',ondelete='CASCADE'),nullable=False),
      sa.Column('position',sa.Integer(),nullable=False),
      sa.Column('excerpt',sa.Text(),nullable=False),
      sa.Column('embedding',Vector(384),nullable=False),
      sa.Column('model_id',sa.String(128),nullable=False),
      sa.UniqueConstraint('document_id','position',name='uq_p4_chunk_document_position'))
    op.create_index('ix_p4_chunk_doc','phase4_chunks',['document_id'])
    op.create_table('phase4_reviews',
      sa.Column('id',sa.Uuid(),primary_key=True),
      sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
      sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
      sa.Column('application_id',sa.Uuid(),sa.ForeignKey('applications.id',ondelete='CASCADE'),nullable=False),
      sa.Column('note',sa.String(2000),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))

def downgrade():
    # Review before downgrading: this deletes extracted evidence and review notes.
    op.drop_table('phase4_reviews')
    op.drop_index('ix_p4_chunk_doc','phase4_chunks')
    op.drop_table('phase4_chunks')
    op.drop_index('ix_p4_docs_candidate','phase4_documents')
    op.drop_table('phase4_documents')
