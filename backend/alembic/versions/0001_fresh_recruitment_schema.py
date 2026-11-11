"""Fresh recruitment schema - 16 application tables, vector extension, and role categories.

Revision ID: 0001_fresh_schema
Revises:
"""
from alembic import op
from sqlalchemy.orm import Session
from app.models.schema import Base
from app.models.categories import seed_official_roles

revision = "0001_fresh_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("This migration is intended for PostgreSQL with pgvector")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # SQLAlchemy metadata is shared with Alembic autogenerate for future revisions.
    for table in Base.metadata.sorted_tables:
        table.create(bind=bind, checkfirst=False)
    session = Session(bind=bind)
    try:
        seed_official_roles(session)
        session.flush()
    finally:
        session.close()


def downgrade():
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=False)
    # Intentionally leave the vector extension installed; other schemas may use it.
