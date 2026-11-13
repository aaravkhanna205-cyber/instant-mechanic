"""Pure function tests; full SMTP/live endpoint verification still required."""
import pytest
from app.phase6_agents import tracking


def test_tracking_disabled_by_default(monkeypatch):
    monkeypatch.delenv('PHASE6_TRACKING_ENABLED', raising=False)
    assert tracking.enabled() is False


def test_notice_confirmation_required(monkeypatch):
    monkeypatch.setenv('PHASE6_TRACKING_ENABLED','YES')
    monkeypatch.delenv('PHASE6_TRACKING_NOTICE_CONFIRMED', raising=False)
    assert tracking.enabled() is False


def test_safe_html_rendering():
    result = tracking.render_html('<script>alert(1)</script>\nThanks', ('https://example.test/c/opaque','https://example.test/o/opaque.gif'))
    assert '<script>' not in result
    assert '&lt;script&gt;' in result
    assert 'engagement-tracked' in result


def test_destination_is_fixed_at_prepare_time(monkeypatch):
    monkeypatch.setenv('PHASE6_TRACKING_PUBLIC_BASE_URL','https://app.example.test')
    monkeypatch.setenv('PHASE6_TRACKING_DESTINATION','https://evil.example.test')
    class DummyProposal:
        organization_id = 'org'
        id = 'prop'
    monkeypatch.setenv('PHASE6_TRACKING_ENABLED','YES')
    monkeypatch.setenv('PHASE6_TRACKING_NOTICE_CONFIRMED','YES')
    with pytest.raises(ValueError):
        tracking.prepare(None, DummyProposal())


def test_http_destination_is_rejected(monkeypatch):
    monkeypatch.setenv('PHASE6_TRACKING_PUBLIC_BASE_URL','https://app.example.test')
    monkeypatch.setenv('PHASE6_TRACKING_DESTINATION','http://app.example.test/portal')
    monkeypatch.setenv('PHASE6_TRACKING_ENABLED','YES')
    monkeypatch.setenv('PHASE6_TRACKING_NOTICE_CONFIRMED','YES')
    class DummyProposal:
        organization_id = 'org'
        id = 'prop'
    with pytest.raises(ValueError):
        tracking.prepare(None, DummyProposal())
