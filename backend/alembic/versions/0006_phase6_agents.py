"""Phase 6 persistent, human-approved recruitment automation

Revision ID: 0006_phase6_agents
Revises: 0005_interview_studio
"""
from alembic import op
import sqlalchemy as sa
revision='0006_phase6_agents'
down_revision='0005_interview_studio'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('phase6_proposals',
       sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
       sa.Column('created_by_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('reviewed_by_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('target_type',sa.String(30),nullable=False),sa.Column('target_id',sa.Uuid(),nullable=False),
       sa.Column('kind',sa.String(40),nullable=False),sa.Column('title',sa.String(200),nullable=False),
       sa.Column('draft',sa.Text(),nullable=False),sa.Column('recipient_user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('state',sa.String(24),nullable=False,server_default='pending'),
       sa.Column('approval_note',sa.Text()),sa.Column('dedupe_key',sa.String(160),nullable=False),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
       sa.Column('reviewed_at',sa.DateTime(timezone=True)),sa.Column('scheduled_for',sa.DateTime(timezone=True)),
       sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
       sa.Column('next_attempt_at',sa.DateTime(timezone=True)),sa.Column('last_error',sa.Text()),
       sa.UniqueConstraint('organization_id','dedupe_key',name='uq_p6_org_dedupe'))
    op.create_index('ix_p6_proposals_organization_id','phase6_proposals',['organization_id'])
    op.create_index('ix_p6_proposals_state_due','phase6_proposals',['state','next_attempt_at'])
    op.create_table('phase6_events',
       sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
       sa.Column('proposal_id',sa.Uuid(),sa.ForeignKey('phase6_proposals.id',ondelete='SET NULL')),
       sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('event',sa.String(80),nullable=False),sa.Column('details',sa.JSON(),nullable=False),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_p6_events_organization_id','phase6_events',['organization_id'])
    op.create_table('phase6_knowledge',
       sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
       sa.Column('created_by_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('title',sa.String(180),nullable=False),sa.Column('body',sa.Text(),nullable=False),
       sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_p6_knowledge_organization_id','phase6_knowledge',['organization_id'])
    op.create_table('phase6_tasks',
       sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
       sa.Column('title',sa.String(240),nullable=False),sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('created_by_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='SET NULL')),
       sa.Column('status',sa.String(24),nullable=False,server_default='open'),sa.Column('due_at',sa.DateTime(timezone=True)),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_p6_tasks_organization_id','phase6_tasks',['organization_id'])
    op.create_table('phase6_deliveries',
       sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('proposal_id',sa.Uuid(),sa.ForeignKey('phase6_proposals.id',ondelete='CASCADE'),nullable=False,unique=True),
       sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
       sa.Column('recipient_email',sa.String(320),nullable=False),sa.Column('mode',sa.String(30),nullable=False),
       sa.Column('status',sa.String(30),nullable=False),sa.Column('reference',sa.String(300)),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_p6_deliveries_organization_id','phase6_deliveries',['organization_id'])

def downgrade():
    # This deletes automation history. Never downgrade in production without explicit data backup.
    op.drop_table('phase6_deliveries');op.drop_table('phase6_tasks');op.drop_table('phase6_knowledge');op.drop_table('phase6_events');op.drop_table('phase6_proposals')
