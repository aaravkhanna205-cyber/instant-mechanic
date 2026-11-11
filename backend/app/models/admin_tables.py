"""Core table handles for the administration tables created by Alembic.

Migrations 0002 and 0003 own the real schema (foreign keys, indexes). These
definitions exist so API code can use portable SQLAlchemy Core statements
instead of PostgreSQL-only SQL strings, which also lets the isolated SQLite
tests cover the import and privacy endpoints.

They live in their own MetaData on purpose: ``Base.metadata`` keeps exactly
the 16 recruitment tables.
"""
from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, Uuid, false, func,
)

admin_metadata = MetaData()

import_batches = Table(
    "import_batches", admin_metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("organization_id", Uuid(as_uuid=True), nullable=False),
    Column("created_by_id", Uuid(as_uuid=True)),
    Column("filename", String(240), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

import_rows = Table(
    "import_rows", admin_metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("batch_id", Uuid(as_uuid=True), nullable=False, index=True),
    Column("row_number", Integer, nullable=False),
    Column("job_id", Uuid(as_uuid=True)),
    Column("error", Text),
    Column("data", JSON, nullable=False),
    # Added by migration 0003 for candidate imports.
    Column("user_id", Uuid(as_uuid=True)),
    Column("application_id", Uuid(as_uuid=True)),
    Column("created_user", Boolean, nullable=False, server_default=false()),
)

password_reset_requests = Table(
    "password_reset_requests", admin_metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("user_id", Uuid(as_uuid=True), nullable=False),
    Column("token_digest", String(64), unique=True, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True)),
)

data_deletion_requests = Table(
    "data_deletion_requests", admin_metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("user_id", Uuid(as_uuid=True), nullable=False),
    Column("status", String(32), nullable=False, server_default="pending"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    # Added by migration 0003.
    Column("reason", Text),
    Column("decided_by_id", Uuid(as_uuid=True)),
    Column("decided_at", DateTime(timezone=True)),
    Column("decision_note", Text),
)
