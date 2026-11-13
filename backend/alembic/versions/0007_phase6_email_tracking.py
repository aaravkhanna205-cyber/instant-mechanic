"""Optional Phase 6 email engagement tracking.

Revision ID: 0007_phase6_email_tracking
Revises: 0006_phase6_agents
"""
from alembic import op
import sqlalchemy as sa
revision = '0007_phase6_email_tracking'
down_revision = '0006_phase6_agents'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('phase6_tracking',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('proposal_id',sa.Uuid(),sa.ForeignKey('phase6_proposals.id',ondelete='CASCADE'),nullable=False),
        sa.Column('token_digest',sa.String(64),unique=True,nullable=False),
        sa.Column('kind',sa.String(12),nullable=False),
        sa.Column('destination_url',sa.String(1000)),
        sa.Column('count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('first_seen_at',sa.DateTime(timezone=True)),
        sa.Column('last_seen_at',sa.DateTime(timezone=True)),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_phase6_tracking_organization_id','phase6_tracking',['organization_id'])
    op.create_index('ix_phase6_tracking_proposal_id','phase6_tracking',['proposal_id'])

def downgrade():
    op.drop_table('phase6_tracking')
