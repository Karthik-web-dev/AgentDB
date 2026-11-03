"""Novelty 2: append-only observability history (events, logs, metrics, runs)."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.event import Event
from app.models.log import Log
from app.models.metric import Metric


def _auth(user):
    return {"Authorization": user["Authorization"]}


@pytest.fixture()
def history(client, db_session, user_a, agent_a):
    """One run with one event, one log and one metric, all written through the normal paths."""
    run = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]}).json()
    event = Event(run_id=run["id"], event_type="tool", event_name="search", payload={"q": "x"})
    log = Log(
        run_id=run["id"],
        agent_id=agent_a["id"],
        severity="INFO",
        message="started",
        metadata_=None,
        timestamp=datetime(2026, 10, 1, 9, 0, 0),
    )
    metric = Metric(run_id=run["id"], metric_name="latency_ms", metric_value=120.0, unit="ms")
    db_session.add_all([event, log, metric])
    db_session.commit()
    return {"run": run, "event_id": event.id, "log_id": log.id, "metric_id": metric.id}


@pytest.mark.parametrize(
    "table, record_key, statement, message",
    [
        ("events", "event_id", "UPDATE events SET event_name = 'changed' WHERE id = :id", "events are append-only"),
        ("events", "event_id", "DELETE FROM events WHERE id = :id", "events are append-only"),
        ("logs", "log_id", "UPDATE logs SET message = 'changed' WHERE id = :id", "logs are append-only"),
        ("logs", "log_id", "DELETE FROM logs WHERE id = :id", "logs are append-only"),
        ("metrics", "metric_id", "UPDATE metrics SET metric_value = 0 WHERE id = :id", "metrics are append-only"),
        ("metrics", "metric_id", "DELETE FROM metrics WHERE id = :id", "metrics are append-only"),
    ],
)
def test_history_rows_cannot_be_changed_or_removed(db_session, history, table, record_key, statement, message):
    with pytest.raises(Exception, match=message):
        db_session.execute(text(statement), {"id": history[record_key]})
        db_session.commit()
    db_session.rollback()


def test_run_cannot_be_deleted(db_session, history):
    with pytest.raises(Exception, match="runs are historical"):
        db_session.execute(text("DELETE FROM runs WHERE id = :id"), {"id": history["run"]["id"]})
        db_session.commit()
    db_session.rollback()


def test_run_status_can_still_be_closed(client, user_a, history):
    response = client.patch(
        f"/api/v1/runs/{history['run']['id']}",
        headers=_auth(user_a),
        json={"status": "completed", "execution_time_ms": 500},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_event_update_endpoint_is_gone(client, user_a, history):
    """Events are facts: the API must not offer a way to edit them."""
    response = client.patch(
        f"/api/v1/events/{history['event_id']}",
        headers=_auth(user_a),
        json={"event_name": "rewritten"},
    )
    assert response.status_code == 405
