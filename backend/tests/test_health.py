"""Health endpoint: confirms the API process and the live MySQL connection."""


def test_health_reports_database_connected(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["app"] == "AgentDB"
    assert body["database"] == "connected"


def test_openapi_is_served_under_api_prefix(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in ("/api/v1/auth/register", "/api/v1/agents", "/api/v1/runs", "/api/v1/logs", "/api/v1/metrics"):
        assert any(p.startswith(expected) for p in paths), f"missing route family {expected}"
