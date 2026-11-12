"""Offline guardrails; real PostgreSQL + Redis integration must also be tested."""
import ast
from pathlib import Path
from app.models.schema import Base
from app.models.categories import OFFICIAL_ROLES


def test_original_recruitment_tables():
    # The Interview Studio adds three tables of its own; the original schema stays at 16.
    assert len(set(Base.metadata.tables) - {"interview_questions", "interview_answers", "interview_reports"}) == 16
    assert len(OFFICIAL_ROLES) == 11


def test_management_import_has_preview_and_undo():
    src=Path('app/api/management.py').read_text(encoding='utf-8')
    tree=ast.parse(src)
    names={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert {'preview','commit_import','undo','register','grant_membership','settings_update'} <= names


def test_admin_migration_expands_to_22_tables():
    src=Path('alembic/versions/0002_phase3_admin.py').read_text(encoding='utf-8')
    ast.parse(src)
    for table in ('app_settings','import_batches','import_rows','password_reset_requests','data_deletion_requests','feature_flags'):
        assert f"'{table}'" in src
