"""Events (writable), logs and metrics (read-only): ownership and filtering."""

from datetime import datetime

from app.models.log import Log
from app.models.metric import Metric


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _run(client, user, agent_id):
    response = client.post("/api/v1/runs", headers=_auth(user), json={"agent_id": agent_id})
    assert response.status_code == 201, response.text
    return response.json()


def _event(client, user, run_id, name="tool_call"):
    return client.post(
        "/api/v1/events",
        headers=_auth(user),
        json={"run_id": run_id, "event_type": "tool", "event_name": name, "payload": {"tool": "search"}},
    )


# ---------------------------------------------------------------- events

def test_create_event_on_own_run(client, user_a, agent_a):
    run = _run(client, user_a, agent_a["id"])
    response = _event(client, user_a, run["id"])
    assert response.status_code == 201
    assert response.json()["payload"] == {"tool": "search"}


def test_create_event_on_another_users_run_is_not_found(client, user_a, user_b, agent_a):
    run = _run(client, user_a, agent_a["id"])
    assert _event(client, user_b, run["id"]).status_code == 404


def test_event_list_only_contains_own_events(client, user_a, user_b, agent_a):
    run_a = _run(client, user_a, agent_a["id"])
    _event(client, user_a, run_a["id"], name="mine")
    response = client.get("/api/v1/events", headers=_auth(user_b))
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------- logs

def _insert_log(db_session, run, severity="INFO", message="Run started", metadata=None):
    log = Log(
        run_id=run["id"],
        agent_id=run["agent_id"],
        severity=severity,
        message=message,
        metadata_=metadata,
        timestamp=datetime(2026, 10, 1, 12, 0, 0),
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


def test_get_log_returns_metadata_under_metadata_key(client, db_session, user_a, agent_a):
    """Regression: LogResponse used to fail with 'metadata Field required'."""
    run = _run(client, user_a, agent_a["id"])
    log = _insert_log(db_session, run, severity="ERROR", message="Rate limit", metadata={"status_code": 429})
    response = client.get(f"/api/v1/logs/{log.id}", headers=_auth(user_a))
    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "ERROR"
    assert body["metadata"] == {"status_code": 429}


def test_log_list_filters_by_severity_and_search(client, db_session, user_a, agent_a):
    run = _run(client, user_a, agent_a["id"])
    _insert_log(db_session, run, severity="INFO", message="Run completed")
    _insert_log(db_session, run, severity="ERROR", message="Timeout talking to provider")
    response = client.get(
        "/api/v1/logs", headers=_auth(user_a), params={"severity": "ERROR", "search": "timeout"}
    )
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["message"] == "Timeout talking to provider"


def test_log_from_another_user_is_not_found(client, db_session, user_a, user_b, agent_a):
    run = _run(client, user_a, agent_a["id"])
    log = _insert_log(db_session, run)
    assert client.get(f"/api/v1/logs/{log.id}", headers=_auth(user_b)).status_code == 404


def test_log_list_rejects_out_of_range_limit(client, user_a):
    response = client.get("/api/v1/logs", headers=_auth(user_a), params={"limit": 500})
    assert response.status_code == 422


# ---------------------------------------------------------------- metrics

def _insert_metric(db_session, run, name="latency_ms", value=1200.0):
    metric = Metric(run_id=run["id"], metric_name=name, metric_value=value, unit="ms")
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


def test_metric_list_and_get_for_owner(client, db_session, user_a, agent_a):
    run = _run(client, user_a, agent_a["id"])
    metric = _insert_metric(db_session, run)
    listing = client.get("/api/v1/metrics", headers=_auth(user_a), params={"metric_name": "latency_ms"})
    assert listing.status_code == 200
    assert [m["id"] for m in listing.json()] == [metric.id]
    single = client.get(f"/api/v1/metrics/{metric.id}", headers=_auth(user_a))
    assert single.status_code == 200
    assert single.json()["metric_value"] == 1200.0


def test_metric_from_another_user_is_not_found(client, db_session, user_a, user_b, agent_a):
    run = _run(client, user_a, agent_a["id"])
    metric = _insert_metric(db_session, run)
    assert client.get(f"/api/v1/metrics/{metric.id}", headers=_auth(user_b)).status_code == 404
