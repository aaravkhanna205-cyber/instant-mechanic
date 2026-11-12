"""Interview Studio tables: approved questions, candidate answers, reviewer decision."""
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.schema import Base, new_id, utcnow


class InterviewQuestion(Base):
    """A question exists here only after a recruiter approved it."""
    __tablename__ = "interview_questions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)
    interview_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    __table_args__ = (UniqueConstraint("interview_id", "position", name="uq_interview_question_position"),)


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    interview_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())


class InterviewReport(Base):
    """The human reviewer's decision on a completed interview. Never set automatically."""
    __tablename__ = "interview_reports"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_id)
    interview_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    __table_args__ = (CheckConstraint("decision IN ('advance','hold','reject')", name="interview_report_decision"),)
