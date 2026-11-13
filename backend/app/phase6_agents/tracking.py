"""Privacy-conscious engagement signals for approved Phase 6 SMTP messages.

Public tokens never contain email addresses, and only their SHA-256 digests are stored.
A click is redirected to one fixed, operator-configured candidate-portal URL.
"""
import hashlib
import html
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from sqlalchemy import select
from .models import AgentTracking, AgentDelivery

PIXEL = bytes.fromhex('47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b')

def _on(key):
    return os.getenv(key, '').strip().upper() == 'YES'

def _https_url(name):
    value = os.getenv(name, '').strip().rstrip('/')
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment:
        raise ValueError(f'{name} must be a full HTTPS URL without user credentials or fragment')
    return value

def enabled():
    return _on('PHASE6_TRACKING_ENABLED') and _on('PHASE6_TRACKING_NOTICE_CONFIRMED')

def _token():
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()

def _record(db, proposal, kind, destination_url=None):
    raw, digest = _token()
    db.add(AgentTracking(organization_id=proposal.organization_id, proposal_id=proposal.id,
                         token_digest=digest, kind=kind, destination_url=destination_url,
                         expires_at=datetime.now(timezone.utc)+timedelta(days=30)))
    return raw

def prepare(db, proposal):
    """Create tokens before SMTP transmission. Caller commits before sending email."""
    if not enabled():
        return None
    public_base = _https_url('PHASE6_TRACKING_PUBLIC_BASE_URL')
    destination = _https_url('PHASE6_TRACKING_DESTINATION')
    # Do not redirect recipients to arbitrary third-party websites.
    if urlparse(public_base).hostname != urlparse(destination).hostname:
        raise ValueError('Tracking destination must use the same hostname as the application')
    click_token = _record(db, proposal, 'click', destination_url=destination)
    click_url = f'{public_base}/api/phase6/organizations/{proposal.organization_id}/track/c/{click_token}'
    pixel_url = None
    if _on('PHASE6_OPEN_TRACKING_ENABLED'):
        open_token = _record(db, proposal, 'open')
        pixel_url = f'{public_base}/api/phase6/organizations/{proposal.organization_id}/track/o/{open_token}.gif'
    return click_url, pixel_url

def render_html(approved_text, links):
    if links is None:
        return None
    click_url, pixel_url = links
    body = html.escape(approved_text).replace('\n', '<br>')
    footer = ('This message contains an engagement-tracked portal link'
              + (' and an email-open image' if pixel_url else '')
              + '. Automated privacy/security tools may trigger these signals.')
    return ('<!doctype html><html><body>'
            f'<div style="white-space:normal">{body}</div>'
            f'<p><a href="{html.escape(click_url, quote=True)}">Open your candidate portal (tracked link)</a></p>'
            f'<p style="font-size:12px;color:#555">{html.escape(footer)}</p>'
            + (f'<img src="{html.escape(pixel_url, quote=True)}" width="1" height="1" alt="" />' if pixel_url else '')
            + '</body></html>')

def destination(db, organization_id, token):
    """Redirect only to the fixed HTTPS destination validated at send time."""
    digest = hashlib.sha256(token.encode('ascii', errors='ignore')).hexdigest()
    row = db.scalar(select(AgentTracking).where(AgentTracking.organization_id == organization_id,
        AgentTracking.token_digest == digest, AgentTracking.kind == 'click'))
    if row and row.destination_url and urlparse(row.destination_url).scheme == 'https':
        return row.destination_url
    return '/portal'  # Local fallback, never an attacker-controlled redirect.

def observe(db, organization_id, token, kind):
    if _on('PHASE6_TRACKING_API_DISABLED') or len(token) > 128 or len(token) < 32:
        return False
    digest = hashlib.sha256(token.encode('ascii', errors='ignore')).hexdigest()
    now = datetime.now(timezone.utc)
    track = db.scalar(select(AgentTracking).where(AgentTracking.organization_id == organization_id,
        AgentTracking.token_digest == digest, AgentTracking.kind == kind).with_for_update())
    if not track:
        return False
    expiry = track.expires_at if track.expires_at.tzinfo else track.expires_at.replace(tzinfo=timezone.utc)
    if expiry.astimezone(timezone.utc) < now:
        return False
    delivery = db.scalar(select(AgentDelivery).where(AgentDelivery.proposal_id == track.proposal_id,
                                               AgentDelivery.status == 'smtp_accepted'))
    if delivery is None:
        return False
    # Persist aggregate only: no IP addresses, user agents, or recipient IDs in event logs.
    if track.first_seen_at is None:
        track.first_seen_at = now
    track.last_seen_at = now
    track.count = min(track.count + 1, 10000)
    db.commit()
    return True
