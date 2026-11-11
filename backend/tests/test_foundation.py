from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_is_independent_of_services():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["phase"] == "3-foundation"


def test_readiness_success(monkeypatch):
    monkeypatch.setattr("app.api.system.check_dependencies", lambda: {"postgres": True, "redis": True})
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_rejects_failed_dependency(monkeypatch):
    monkeypatch.setattr("app.api.system.check_dependencies", lambda: {"postgres": False, "redis": True})
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["postgres"] is False


def test_cors_development_origin():
    response = client.options("/api/health", headers={
        "Origin": "http://127.0.0.1:3003",
        "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3003"
    assert response.headers["access-control-allow-credentials"] == "true"
