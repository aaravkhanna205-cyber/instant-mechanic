"""DB, Redis and authenticated authorization dependencies."""
from collections.abc import Iterator
from functools import lru_cache
from uuid import UUID
import redis
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.models.schema import User, OrganizationMembership, Organization
from app.security.sessions import SessionRecord, COOKIE_NAME, read_session


@lru_cache(maxsize=1)
def session_factory():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL missing")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def get_redis() -> Iterator[redis.Redis]:
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL missing")
    client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
    try:
        yield client
    finally:
        client.close()


def get_session_record(request: Request, cache: redis.Redis = Depends(get_redis)) -> SessionRecord:
    record = read_session(cache, request.cookies.get(COOKIE_NAME))
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return record


def get_current_user(db: Session = Depends(get_db), record: SessionRecord = Depends(get_session_record)) -> User:
    user = db.get(User, record.user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return user


def require_recruiter_for_org(organization_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
    if user.is_platform_admin:
        return user
    org = db.get(Organization, organization_id)
    if not org or not org.active:
        raise HTTPException(status_code=404, detail="Organization not found")
    roles = db.scalars(select(OrganizationMembership.role).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == organization_id
    )).all()
    if not any(r in ("owner", "admin", "recruiter") for r in roles):
        raise HTTPException(status_code=403, detail="Access denied")
    return user
