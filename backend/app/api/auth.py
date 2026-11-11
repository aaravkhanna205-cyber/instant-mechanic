"""Browser login, logout, identity, and scoped RBAC checks."""
import hashlib
import hmac
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from redis import Redis
from app.core.config import settings
from app.models.schema import User, OrganizationMembership
from app.security.passwords import verify_password
from app.security.sessions import (
    COOKIE_NAME, create_session, cookie_options, read_session, revoke_session,
)
from app.security.dependencies import (
    get_db, get_redis, get_current_user, require_platform_admin,
    require_recruiter_for_org, get_session_record,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    # Browser clients submit JSON, which requires a preflight between origins.
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(status_code=415, detail="JSON required")


def public_user(user: User, db: Session) -> dict:
    roles = db.execute(select(OrganizationMembership.organization_id, OrganizationMembership.role).where(
        OrganizationMembership.user_id == user.id
    )).all()
    return {
        "id": str(user.id), "email": user.email, "full_name": user.full_name,
        "is_platform_admin": user.is_platform_admin,
        "memberships": [{"organization_id": str(org), "role": role} for org, role in roles],
    }


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response,
          db: Session = Depends(get_db), cache: Redis = Depends(get_redis)):
    check_origin(request)
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Shared lockout for each account; fail closed when Redis is unavailable.
    key = "imhire:loginfail:" + hashlib.sha256(email.encode()).hexdigest()
    failures = int(cache.get(key) or 0)
    if failures >= 8:
        raise HTTPException(status_code=429, detail="Too many attempts. Try later")
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(user.password_hash if user else None, payload.password) or not user or not user.active:
        failures = cache.incr(key)
        if failures == 1:
            cache.expire(key, 900)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    cache.delete(key)
    old = request.cookies.get(COOKIE_NAME)
    if old:
        revoke_session(cache, old)
    token, record = create_session(cache, user.id)
    response.set_cookie(COOKIE_NAME, token, **cookie_options())
    return {"user": public_user(user, db), "csrf_token": record.csrf}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user),
       cache: Redis = Depends(get_redis)):
    record = read_session(cache, request.cookies.get(COOKIE_NAME))
    if not record:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"user": public_user(user, db), "csrf_token": record.csrf}


@router.post("/logout")
def logout(request: Request, response: Response, record = Depends(get_session_record),
           cache: Redis = Depends(get_redis)):
    check_origin(request)
    csrf = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(csrf, record.csrf):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    revoke_session(cache, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", secure=cookie_options()["secure"], samesite=cookie_options()["samesite"])
    return {"ok": True}


@router.get("/admin-check")
def admin_check(user: User = Depends(require_platform_admin)):
    return {"ok": True, "user_id": str(user.id), "scope": "platform_admin"}


@router.get("/organizations/{organization_id}/recruiter-check")
def recruiter_check(organization_id: UUID, user: User = Depends(require_recruiter_for_org)):
    return {"ok": True, "user_id": str(user.id), "organization_id": str(organization_id)}
