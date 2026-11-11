"""Candidate import tracking and data-deletion decisions.

Revision ID: 0003_phase3_completion
Revises: 0002_phase3_admin

Additive only: new nullable columns (or columns with a server default) on two
existing administration tables. No data is rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_phase3_completion"
down_revision = "0002_phase3_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_rows", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("import_rows", sa.Column("application_id", sa.Uuid(), nullable=True))
    op.add_column("import_rows", sa.Column("created_user", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_import_rows_user_id_users", "import_rows", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_import_rows_application_id_applications", "import_rows", "applications", ["application_id"], ["id"], ondelete="SET NULL")

    op.add_column("data_deletion_requests", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("data_deletion_requests", sa.Column("decided_by_id", sa.Uuid(), nullable=True))
    op.add_column("data_deletion_requests", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("data_deletion_requests", sa.Column("decision_note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_data_deletion_requests_decided_by_id_users", "data_deletion_requests", "users", ["decided_by_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_data_deletion_requests_user_id", "data_deletion_requests", ["user_id"])


def downgrade():
    op.drop_index("ix_data_deletion_requests_user_id", table_name="data_deletion_requests")
    op.drop_constraint("fk_data_deletion_requests_decided_by_id_users", "data_deletion_requests", type_="foreignkey")
    for column in ("decision_note", "decided_at", "decided_by_id", "reason"):
        op.drop_column("data_deletion_requests", column)
    op.drop_constraint("fk_import_rows_application_id_applications", "import_rows", type_="foreignkey")
    op.drop_constraint("fk_import_rows_user_id_users", "import_rows", type_="foreignkey")
    for column in ("created_user", "application_id", "user_id"):
        op.drop_column("import_rows", column)
