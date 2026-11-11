from fastapi import APIRouter, HTTPException, status

from app.services.dependencies import check_dependencies

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health")
def health() -> dict[str, str]:
    # Liveness: does not require PostgreSQL or Redis to be available.
    return {"status": "ok", "phase": "3-foundation"}


@router.get("/ready")
def ready() -> dict[str, object]:
    # Readiness: checks actual DB and cache connections, without exposing secrets.
    checks = check_dependencies()
    if not all(checks.values()):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail={"status": "unavailable", "checks": checks})
    return {"status": "ready", "checks": checks}
