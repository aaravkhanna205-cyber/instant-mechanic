from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.system import router as system_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Instant Mechanic Hire API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
)
app.include_router(system_router)

from app.api.auth import router as auth_router
app.include_router(auth_router)

from app.api.recruitment import router as recruitment_router
app.include_router(recruitment_router)
from app.api.management import router as management_router, reg as registration_router
app.include_router(management_router)
app.include_router(registration_router)
from app.api.password_reset import router as recovery_router
app.include_router(recovery_router)
from app.api.candidate_import import router as candidate_import_router
app.include_router(candidate_import_router)
from app.api.privacy import router as privacy_router, admin_router as privacy_admin_router
app.include_router(privacy_router)
app.include_router(privacy_admin_router)

# Phase 4 human-reviewed AI assistance
from app.phase4_ai.api import router as phase4_router
app.include_router(phase4_router)

# Interview Studio: scheduling, approved question sets, candidate session, review report
from app.interview_studio.api import router as interview_studio_router
app.include_router(interview_studio_router)
