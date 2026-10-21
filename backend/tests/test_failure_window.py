"""Novelty 4: sliding-window failure rules ("N failed runs within M minutes")."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.models.run import Run


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _failure_rule(client, user, threshold=5, window=10, agent_id=None):
    body = {
        "rule_name": "Failure burst",
        "rule_type": "failure_window",
        "threshold_value": threshold,
        "time_window_minutes": window,
    }
    if agent_id is not None:
        body["agent_id"] = agent_id
    response = client.post("/api/v1/alerts", headers=_auth(user), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _fail_run(client, user, agent_id):
    """Create a run and close it as failed through the API, which exercises the UPDATE trigger."""
    run = client.post("/api/v1/runs", headers=_auth(user), json={"agent_id": agent_id}).json()
    response = client.patch(f"/api/v1/runs/{run['id']}", headers=_auth(user), json={"status": "failed"})
    assert response.status_code == 200, response.text
    return run


def _firings(client, user, alert_id):
    return client.get(f"/api/v1/alerts/{alert_id}/firings", headers=_auth(user)).json()


def _alert(client, user, alert_id):
    return client.get(f"/api/v1/alerts/{alert_id}", headers=_auth(user)).json()


def test_fifth_failure_fires_and_fourth_does_not(client, user_a, agent_a):
    rule = _failure_rule(client, user_a, agent_id=agent_a["id"])
    for _ in range(4):
        _fail_run(client, user_a, agent_a["id"])
    assert _firings(client, user_a, rule["id"]) == []
    fifth = _fail_run(client, user_a, agent_a["id"])

    firings = _firings(client, user_a, rule["id"])
    assert len(firings) == 1
    assert firings[0]["run_id"] == fifth["id"]
    assert firings[0]["metric_id"] is None
    assert firings[0]["observed_value"] == 5
    assert _alert(client, user_a, rule["id"])["status"] == "triggered"


def test_successful_runs_do_not_count(client, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=2, agent_id=agent_a["id"])
    _fail_run(client, user_a, agent_a["id"])
    for _ in range(5):
        run = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]}).json()
        client.patch(f"/api/v1/runs/{run['id']}", headers=_auth(user_a), json={"status": "completed"})
    assert _firings(client, user_a, rule["id"]) == []


def test_failures_outside_the_window_are_not_counted(client, db_session, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=3, window=10, agent_id=agent_a["id"])
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    db_session.add_all(
        [Run(agent_id=agent_a["id"], status="failed", started_at=old, completed_at=old) for _ in range(5)]
    )
    db_session.commit()
    _fail_run(client, user_a, agent_a["id"])
    _fail_run(client, user_a, agent_a["id"])
    assert _firings(client, user_a, rule["id"]) == []  # only 2 recent failures, threshold is 3
    _fail_run(client, user_a, agent_a["id"])
    assert len(_firings(client, user_a, rule["id"])) == 1


def test_failure_inserted_as_failed_also_counts(client, db_session, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=1, agent_id=agent_a["id"])
    db_session.add(Run(agent_id=agent_a["id"], status="failed", started_at=datetime.now(timezone.utc).replace(tzinfo=None), completed_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db_session.commit()
    assert len(_firings(client, user_a, rule["id"])) == 1


def test_same_run_never_fires_twice(client, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=1, agent_id=agent_a["id"])
    run = _fail_run(client, user_a, agent_a["id"])
    client.patch(f"/api/v1/runs/{run['id']}", headers=_auth(user_a), json={"status": "failed", "error_message": "again"})
    assert len(_firings(client, user_a, rule["id"])) == 1


def test_agent_scoped_rule_ignores_failures_of_other_agents(client, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=2, agent_id=agent_a["id"])
    other = client.post("/api/v1/agents", headers=_auth(user_a), json={"name": "Other", "model": "m"}).json()
    _fail_run(client, user_a, other["id"])
    _fail_run(client, user_a, other["id"])
    assert _firings(client, user_a, rule["id"]) == []


def test_global_rule_counts_failures_across_own_agents(client, user_a, agent_a):
    rule = _failure_rule(client, user_a, threshold=3)
    other = client.post("/api/v1/agents", headers=_auth(user_a), json={"name": "Other", "model": "m"}).json()
    _fail_run(client, user_a, agent_a["id"])
    _fail_run(client, user_a, other["id"])
    _fail_run(client, user_a, agent_a["id"])
    assert len(_firings(client, user_a, rule["id"])) == 1


def test_global_rule_never_counts_another_users_failures(client, user_a, user_b, agent_a):
    rule = _failure_rule(client, user_a, threshold=2)
    agent_b = client.post("/api/v1/agents", headers=_auth(user_b), json={"name": "BobBot", "model": "m"}).json()
    _fail_run(client, user_b, agent_b["id"])
    _fail_run(client, user_b, agent_b["id"])
    _fail_run(client, user_b, agent_b["id"])
    assert _firings(client, user_a, rule["id"]) == []


@pytest.mark.parametrize("bad_threshold", [0, 2.5, -1])
def test_failure_rule_threshold_must_be_a_positive_whole_number(client, user_a, bad_threshold):
    response = client.post(
        "/api/v1/alerts",
        headers=_auth(user_a),
        json={"rule_name": "x", "rule_type": "failure_window", "threshold_value": bad_threshold, "time_window_minutes": 10},
    )
    assert response.status_code == 422


def test_threshold_rule_still_requires_metric_and_operator(client, user_a):
    response = client.post(
        "/api/v1/alerts",
        headers=_auth(user_a),
        json={"rule_name": "x", "rule_type": "threshold", "threshold_value": 5},
    )
    assert response.status_code == 422


def test_failure_rule_has_fixed_metric_and_operator(client, user_a):
    rule = _failure_rule(client, user_a)
    assert rule["rule_type"] == "failure_window"
    assert rule["metric_name"] == "run_failures"
    assert rule["condition_operator"] == ">="
