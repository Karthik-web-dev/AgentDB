"""The demo dataset must make every dashboard source show real, database-produced data."""

from app.demo_data import DEMO_EMAIL, DEMO_PASSWORD, load_demo_data


def test_demo_data_populates_the_dashboard_sources(client, db_session):
    assert load_demo_data(db_session) is True

    login = client.post("/api/v1/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    agents = client.get("/api/v1/agents", headers=headers).json()
    assert len(agents) == 4
    assert {a["status"] for a in agents} >= {"active", "maintenance"}

    runs = client.get("/api/v1/runs", headers=headers, params={"limit": 100}).json()
    assert len(runs) >= 100
    assert {r["status"] for r in runs} >= {"completed", "failed", "running"}

    overview = client.get("/api/v1/analytics/overview", headers=headers).json()
    assert len(overview) == 4
    assert sum(row["runs_failed"] for row in overview) > 0

    alerts = client.get("/api/v1/alerts", headers=headers).json()
    triggered = [a for a in alerts if a["status"] == "triggered"]
    assert {a["rule_name"] for a in triggered} >= {"Slow responses", "Failure burst"}
    assert any(a["status"] == "disabled" for a in alerts)

    cost = client.get("/api/v1/analytics/cost", headers=headers).json()
    assert sum(row["total_cost_usd"] for row in cost) > 0

    anomalies = client.get("/api/v1/analytics/latency-anomalies", headers=headers).json()
    assert len(anomalies) >= 1

    audit = client.get("/api/v1/audit/verify", headers=headers).json()
    assert audit["is_valid"] is True
    assert audit["rows_checked"] >= 2


def test_loading_twice_does_not_duplicate_data(db_session):
    assert load_demo_data(db_session) is True
    assert load_demo_data(db_session) is False
