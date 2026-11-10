"""Phase 3 backend foundation: health endpoint only; no auth or data APIs yet."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(title="Instant Mechanic Hire API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

@app.get("/api/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "backend-scaffold"}
