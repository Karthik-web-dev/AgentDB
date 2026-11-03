"""Novelty 3: in-database alert engine (sp_evaluate_metric_alerts + metric trigger)."""

import pytest
from app.models.metric import Metric


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _run(client, user, agent_id):
    response = client.post("/api/v1/runs", headers=_auth(user), json={"agent_id": agent_id})
    assert response.status_code == 201, response.text
    return response.json()


def _metric(db_session, run, value, name="latency_ms"):
    # End any transaction left open by an earlier read so this insert runs in a fresh snapshot.
    db_session.rollback()
    metric = Metric(run_id=run["id"], metric_name=name, metric_value=value, unit="ms")
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


def _rule(client, user, **overrides):
    body = {
        "rule_name": "Slow responses",
        "metric_name": "latency_ms",
        "condition_operator": ">",
        "threshold_value": 2000,
    }
    body.update(overrides)
    response = client.post("/api/v1/alerts", headers=_auth(user), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _firings(client, user, alert_id):
    response = client.get(f"/api/v1/alerts/{alert_id}/firings", headers=_auth(user))
    assert response.status_code == 200, response.text
    return response.json()


def test_metric_above_threshold_fires_and_marks_rule_triggered(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    run = _run(client, user_a, agent_a["id"])
    metric = _metric(db_session, run, 2500.0)

    firings = _firings(client, user_a, rule["id"])
    assert len(firings) == 1
    assert firings[0]["metric_id"] == metric.id
    assert firings[0]["observed_value"] == 2500.0
    assert firings[0]["threshold_value"] == 2000.0

    current = client.get(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_a)).json()
    assert current["status"] == "triggered"
    assert current["last_triggered_at"] is not None


def test_metric_below_threshold_does_not_fire(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    _metric(db_session, _run(client, user_a, agent_a["id"]), 900.0)
    assert _firings(client, user_a, rule["id"]) == []
    assert client.get(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_a)).json()["status"] == "active"


@pytest.mark.parametrize(
    "operator, threshold, value, should_fire",
    [
        (">", 100.0, 100.0, False),
        (">=", 100.0, 100.0, True),
        ("<", 100.0, 99.0, True),
        ("<=", 100.0, 101.0, False),
        ("==", 100.0, 100.0, True),
        ("!=", 100.0, 100.0, False),
    ],
)
def test_every_operator_is_evaluated_in_sql(client, db_session, user_a, agent_a, operator, threshold, value, should_fire):
    rule = _rule(client, user_a, agent_id=agent_a["id"], condition_operator=operator, threshold_value=threshold)
    _metric(db_session, _run(client, user_a, agent_a["id"]), value)
    assert (len(_firings(client, user_a, rule["id"])) == 1) is should_fire


def test_metric_name_must_match(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"], metric_name="tokens_used")
    _metric(db_session, _run(client, user_a, agent_a["id"]), 9999.0, name="latency_ms")
    assert _firings(client, user_a, rule["id"]) == []


def test_global_rule_covers_all_own_agents(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a)  # no agent_id: global
    second = client.post("/api/v1/agents", headers=_auth(user_a), json={"name": "Second", "model": "m"}).json()
    _metric(db_session, _run(client, user_a, agent_a["id"]), 3000.0)
    _metric(db_session, _run(client, user_a, second["id"]), 3100.0)
    assert len(_firings(client, user_a, rule["id"])) == 2


def test_global_rule_never_fires_on_another_users_agent(client, db_session, user_a, user_b, agent_a):
    """Isolation: user A's global rule must not evaluate user B's metrics."""
    rule_a = _rule(client, user_a)
    agent_b = client.post("/api/v1/agents", headers=_auth(user_b), json={"name": "BobBot", "model": "m"}).json()
    _metric(db_session, _run(client, user_b, agent_b["id"]), 9000.0)
    assert _firings(client, user_a, rule_a["id"]) == []


def test_agent_specific_rule_ignores_other_agents(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    other = client.post("/api/v1/agents", headers=_auth(user_a), json={"name": "Other", "model": "m"}).json()
    _metric(db_session, _run(client, user_a, other["id"]), 5000.0)
    assert _firings(client, user_a, rule["id"]) == []


def test_disabled_rule_does_not_fire(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    client.patch(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_a), json={"status": "disabled"})
    _metric(db_session, _run(client, user_a, agent_a["id"]), 5000.0)
    assert _firings(client, user_a, rule["id"]) == []


def test_resolved_rule_stops_firing_until_reactivated(client, db_session, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    _metric(db_session, _run(client, user_a, agent_a["id"]), 2500.0)
    resolved = client.post(f"/api/v1/alerts/{rule['id']}/resolve", headers=_auth(user_a)).json()
    assert resolved["status"] == "resolved"
    _metric(db_session, _run(client, user_a, agent_a["id"]), 2600.0)
    assert len(_firings(client, user_a, rule["id"])) == 1

    client.patch(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_a), json={"status": "active"})
    _metric(db_session, _run(client, user_a, agent_a["id"]), 2700.0)
    assert len(_firings(client, user_a, rule["id"])) == 2


def test_api_rejects_unknown_operator(client, user_a, agent_a):
    response = client.post(
        "/api/v1/alerts",
        headers=_auth(user_a),
        json={"rule_name": "x", "metric_name": "latency_ms", "condition_operator": "=>", "threshold_value": 1, "agent_id": agent_a["id"]},
    )
    assert response.status_code == 422


def test_api_refuses_to_set_triggered_directly(client, user_a, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    response = client.patch(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_a), json={"status": "triggered"})
    assert response.status_code == 422


def test_rule_for_another_users_agent_is_not_found(client, user_a, user_b, agent_a):
    response = client.post(
        "/api/v1/alerts",
        headers=_auth(user_b),
        json={"rule_name": "x", "metric_name": "latency_ms", "condition_operator": ">", "threshold_value": 1, "agent_id": agent_a["id"]},
    )
    assert response.status_code == 404


def test_another_users_rule_is_not_found(client, user_a, user_b, agent_a):
    rule = _rule(client, user_a, agent_id=agent_a["id"])
    assert client.get(f"/api/v1/alerts/{rule['id']}", headers=_auth(user_b)).status_code == 404
    assert client.get(f"/api/v1/alerts/{rule['id']}/firings", headers=_auth(user_b)).status_code == 404
