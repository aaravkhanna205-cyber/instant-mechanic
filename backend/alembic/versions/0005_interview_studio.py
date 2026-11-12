"""Interview Studio: scheduling details, approved questions, answers, reviewer decision.

Revision ID: 0005_interview_studio
Revises: 0004_phase4_ai
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_interview_studio'
down_revision = '0004_phase4_ai'
branch_labels = None
depends_on = None


def upgrade():
    # Migration 0001 builds tables from the current models, so on a brand-new database the
    # interview columns already exist when this runs. Every step therefore checks first.
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('interviews')}
    checks = {check['name'] for check in inspector.get_check_constraints('interviews')}
    tables = set(inspector.get_table_names())

    def add(name, column):
        if name not in columns:
            op.add_column('interviews', column)

    add('timezone', sa.Column('timezone', sa.String(64), nullable=False, server_default='Asia/Kolkata'))
    add('duration_minutes', sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='30'))
    add('candidate_response', sa.Column('candidate_response', sa.String(20), nullable=False, server_default='pending'))
    add('candidate_note', sa.Column('candidate_note', sa.Text()))
    add('session_started_at', sa.Column('session_started_at', sa.DateTime(timezone=True)))
    add('session_completed_at', sa.Column('session_completed_at', sa.DateTime(timezone=True)))
    add('reminder_sent_at', sa.Column('reminder_sent_at', sa.DateTime(timezone=True)))
    if 'ck_interviews_interview_candidate_response' not in checks:
        op.create_check_constraint(op.f('ck_interviews_interview_candidate_response'), 'interviews',
                                   "candidate_response IN ('pending','confirmed','declined')")
    if 'ck_interviews_interview_duration' not in checks:
        op.create_check_constraint(op.f('ck_interviews_interview_duration'), 'interviews', 'duration_minutes BETWEEN 10 AND 240')

    if 'interview_questions' not in tables:
        op.create_table(
            'interview_questions',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('interview_id', sa.Uuid(), sa.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('approved_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('interview_id', 'position', name='uq_interview_question_position'),
        )
        op.create_index('ix_interview_questions_interview_id', 'interview_questions', ['interview_id'])

    if 'interview_answers' not in tables:
        op.create_table(
            'interview_answers',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('question_id', sa.Uuid(), sa.ForeignKey('interview_questions.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('interview_id', sa.Uuid(), sa.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('answer', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_interview_answers_interview_id', 'interview_answers', ['interview_id'])

    if 'interview_reports' not in tables:
        op.create_table(
            'interview_reports',
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('interview_id', sa.Uuid(), sa.ForeignKey('interviews.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('decision', sa.String(20), nullable=False),
            sa.Column('decision_note', sa.Text(), nullable=False),
            sa.Column('reviewer_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')),
            sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("decision IN ('advance','hold','reject')", name=op.f('ck_interview_reports_interview_report_decision')),
        )


def downgrade():
    op.drop_table('interview_reports')
    op.drop_index('ix_interview_answers_interview_id', table_name='interview_answers')
    op.drop_table('interview_answers')
    op.drop_index('ix_interview_questions_interview_id', table_name='interview_questions')
    op.drop_table('interview_questions')
    op.drop_constraint(op.f('ck_interviews_interview_duration'), 'interviews', type_='check')
    op.drop_constraint(op.f('ck_interviews_interview_candidate_response'), 'interviews', type_='check')
    for column in ('reminder_sent_at', 'session_completed_at', 'session_started_at', 'candidate_note',
                   'candidate_response', 'duration_minutes', 'timezone'):
        op.drop_column('interviews', column)
