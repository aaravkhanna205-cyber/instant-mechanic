"""Phase 8: record server errors (HTTP 5xx) so the Super Admin can see them in System health.

Only the method, the path (no query string), the status and the error type are kept - never
request bodies, cookies or candidate data. Recording an error must never cause a second error.
"""
from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import DateTime, Integer, String, Uuid, func, select, delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.schema import Base

log = logging.getLogger('imhire.errors')
KEEP_DAYS = 30
_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
_NUM = re.compile(r'/\d+(?=/|$)')
SKIP_PATHS = ('/api/health', '/api/ready')  # readiness probes report outages themselves


class ServerError(Base):
    __tablename__ = 'server_errors'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(200))
    status: Mapped[int] = mapped_column(Integer)
    error_type: Mapped[str] = mapped_column(String(120))


def route_shape(path: str) -> str:
    """'/api/jobs/1b2c...' -> '/api/jobs/{id}' so the same fault groups together and no ids are stored."""
    return _NUM.sub('/{n}', _UUID.sub('{id}', path))[:200]


def record(factory: Callable[[], Session], method: str, path: str, status: int, error_type: str) -> None:
    try:
        with factory() as db:
            db.add(ServerError(method=method[:10], path=route_shape(path), status=status, error_type=error_type[:120]))
            db.execute(delete(ServerError).where(ServerError.created_at < datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)))
            db.commit()
    except Exception as exc:  # noqa: BLE001 - monitoring must never break the request
        log.warning('could not record server error (%s); is migration 0012 applied?', type(exc).__name__)


def install(app, factory: Callable[[], Callable[[], Session]]) -> None:
    """factory() returns a sessionmaker; called lazily so tests and startup without a DB still work.
    Tests can point it elsewhere with app.state.error_session_factory."""
    app.state.error_session_factory = factory

    @app.middleware('http')
    async def server_error_monitor(request: Request, call_next):
        factory = request.app.state.error_session_factory
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            log.exception('unhandled error on %s %s', request.method, request.url.path)
            if not isinstance(exc, OperationalError):  # database down: it cannot be recorded there anyway
                record(lambda: factory()(), request.method, request.url.path, 500, type(exc).__name__)
            return JSONResponse({'detail': 'Something went wrong on our side. Please try again.'}, status_code=500)
        if response.status_code >= 500 and request.url.path not in SKIP_PATHS:
            record(lambda: factory()(), request.method, request.url.path, response.status_code, f'HTTP {response.status_code}')
        return response


def summary(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    day = now - timedelta(days=1)
    try:
        last_24h = db.scalar(select(func.count()).select_from(ServerError).where(ServerError.created_at >= day)) or 0
        last_7d = db.scalar(select(func.count()).select_from(ServerError)
                            .where(ServerError.created_at >= now - timedelta(days=7))) or 0
        top = db.execute(select(ServerError.method, ServerError.path, ServerError.error_type,
                                func.count().label('n'), func.max(ServerError.created_at).label('last'))
                         .where(ServerError.created_at >= now - timedelta(days=7))
                         .group_by(ServerError.method, ServerError.path, ServerError.error_type)
                         .order_by(func.count().desc()).limit(10)).all()
    except Exception:  # noqa: BLE001 - table missing before migration 0012
        db.rollback()
        return {'available': False, 'last_24h': None, 'last_7d': None, 'top': []}
    return {'available': True, 'last_24h': int(last_24h), 'last_7d': int(last_7d),
            'top': [{'method': m, 'path': p, 'error_type': e, 'count': int(n),
                     'last_seen': (l.isoformat() if l else None)} for m, p, e, n, l in top]}
