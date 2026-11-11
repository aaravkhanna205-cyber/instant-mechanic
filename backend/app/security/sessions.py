"""Redis session storage. Redis holds only SHA256 digests of browser tokens."""
import hashlib
import json
import secrets
from dataclasses import dataclass
from uuid import UUID
from redis import Redis
from app.core.config import settings

COOKIE_NAME = "im_hire_session"
SESSION_SECONDS = 8 * 60 * 60


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def redis_key(token: str) -> str:
    return "imhire:sess:" + digest(token)


@dataclass(frozen=True)
class SessionRecord:
    user_id: UUID
    csrf: str


def create_session(redis: Redis, user_id: UUID) -> tuple[str, SessionRecord]:
    token = secrets.token_urlsafe(48)
    record = SessionRecord(user_id=user_id, csrf=secrets.token_urlsafe(32))
    redis.setex(redis_key(token), SESSION_SECONDS, json.dumps({"user_id": str(user_id), "csrf": record.csrf}))
    return token, record


def read_session(redis: Redis, token: str | None) -> SessionRecord | None:
    if not token or len(token) > 256:
        return None
    raw = redis.get(redis_key(token))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return SessionRecord(user_id=UUID(data["user_id"]), csrf=data["csrf"])
    except (ValueError, KeyError, TypeError):
        return None


def revoke_session(redis: Redis, token: str | None) -> None:
    if token:
        redis.delete(redis_key(token))


def cookie_options() -> dict:
    # A cross-site cookie in production requires HTTPS and SameSite=None.
    env = settings.app_env.lower()
    if env in ("production", "prod"):
        return {"httponly": True, "secure": True, "samesite": "none", "path": "/", "max_age": SESSION_SECONDS}
    return {"httponly": True, "secure": False, "samesite": "lax", "path": "/", "max_age": SESSION_SECONDS}
