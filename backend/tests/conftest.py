"""Shared test settings.

Older tests apply to jobs without uploading a resume, so the Phase 8 resume rule is off by default
in tests. Tests that check the rule switch it on with monkeypatch.
"""
import os

os.environ.setdefault('REQUIRE_RESUME_TO_APPLY', 'NO')
