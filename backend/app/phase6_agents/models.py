"""Phase 6 durable workflow records; maps onto the existing application Base."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.schema import Base


def new_id():
    return uuid.uuid4()

class AgentProposal(Base):
    __tablename__ = 'phase6_proposals'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id',ondelete='CASCADE'), nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'), nullable=True)
    target_type: Mapped[str] = mapped_column(String(30),nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),nullable=False)
    kind: Mapped[str] = mapped_column(String(40),nullable=False)
    title: Mapped[str] = mapped_column(String(200),nullable=False)
    draft: Mapped[str] = mapped_column(Text,nullable=False)
    recipient_user_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    state: Mapped[str] = mapped_column(String(24),nullable=False,default='pending',server_default='pending')
    approval_note: Mapped[str|None] = mapped_column(Text,nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160),nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    reviewed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    scheduled_for: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer,default=0,server_default='0',nullable=False)
    next_attempt_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str|None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('organization_id','dedupe_key',name='uq_p6_org_dedupe'),Index('ix_p6_proposals_state_due','state','next_attempt_at'))

class AgentAudit(Base):
    __tablename__='phase6_events'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False,index=True)
    proposal_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('phase6_proposals.id',ondelete='SET NULL'))
    actor_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    event: Mapped[str] = mapped_column(String(80),nullable=False)
    details: Mapped[dict] = mapped_column(JSON,default=dict,nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

class AgentKnowledge(Base):
    __tablename__='phase6_knowledge'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False,index=True)
    created_by_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    title: Mapped[str] = mapped_column(String(180),nullable=False)
    body: Mapped[str] = mapped_column(Text,nullable=False)
    active: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True,server_default='true')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

class AgentTask(Base):
    __tablename__='phase6_tasks'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False,index=True)
    title: Mapped[str] = mapped_column(String(240),nullable=False)
    owner_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    created_by_id: Mapped[uuid.UUID|None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(24),nullable=False,default='open',server_default='open')
    due_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)

class AgentDelivery(Base):
    __tablename__='phase6_deliveries'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=new_id)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('phase6_proposals.id',ondelete='CASCADE'),unique=True,nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id',ondelete='CASCADE'),nullable=False,index=True)
    recipient_email: Mapped[str] = mapped_column(String(320),nullable=False)
    mode: Mapped[str] = mapped_column(String(30),nullable=False)
    status: Mapped[str] = mapped_column(String(30),nullable=False)
    reference: Mapped[str|None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
