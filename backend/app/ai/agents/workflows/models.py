"""Durable workflow runs. Each step's result is saved here, so a run continues after a restart."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.schema import Base

RUN_STATUSES = ('running', 'waiting_resume', 'waiting_interview', 'waiting_review', 'completed', 'failed', 'cancelled')
ACTIVE_STATUSES = ('running', 'waiting_resume', 'waiting_interview', 'waiting_review', 'failed')


def new_id():
    return uuid.uuid4()


class WorkflowRun(Base):
    __tablename__ = 'phase6_workflow_runs'
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    workflow: Mapped[str] = mapped_column(String(40), nullable=False)
    # Set for resume and interview workflows; empty for job description and analytics runs.
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('applications.id', ondelete='CASCADE'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='running', server_default='running')
    # Name of the last step that finished. The next run continues after it.
    step: Mapped[str | None] = mapped_column(String(40))
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    last_error: Mapped[str | None] = mapped_column(Text)
    started_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    review_decision: Mapped[str | None] = mapped_column(String(24))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('ix_p6_runs_org_status', 'organization_id', 'status'),)
