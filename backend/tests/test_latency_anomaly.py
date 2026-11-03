"""Novelty 5: latency anomaly detection with a rolling z-score in SQL."""

from datetime import datetime, timedelta

from app.models.run import Run

BASE_TIME = datetime(2026, 10, 1, 9, 0, 0)
NORMAL = [980, 1000, 1020, 990, 1010, 1005, 995, 1000, 1015, 985, 1002, 998]


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _insert_runs(db_session, agent_id, latencies, status="completed", start_offset_min=0):
    """Insert runs with explicit, evenly spaced start times so window order is deterministic."""
    rows = []
    for i, latency in enumerate(latencies):
        started = BASE_TIME + timedelta(minutes=start_offset_min + i * 5)
        rows.append(
            Run(
                agent_id=agent_id,
                status=status,
                started_at=started,
                completed_at=started + timedelta(milliseconds=latency),
                execution_time_ms=latency,
            )
        )
    db_session.add_all(rows)
    db_session.commit()
    return rows


def _anomalies(client, user, **params):
    response = client.get("/api/v1/analytics/latency-anomalies", headers=_auth(user), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_spike_after_a_stable_baseline_is_flagged(client, db_session, user_a, agent_a):
    runs = _insert_runs(db_session, agent_a["id"], NORMAL + [9000])
    spike = runs[-1]

    flagged = _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0)
    assert [f["run_id"] for f in flagged] == [spike.id]
    assert flagged[0]["latency_ms"] == 9000
    assert flagged[0]["detection_reason"] == "z_score"
    assert flagged[0]["z_score"] > 3
    assert flagged[0]["baseline_size"] == len(NORMAL)


def test_normal_runs_are_not_flagged(client, db_session, user_a, agent_a):
    _insert_runs(db_session, agent_a["id"], NORMAL)
    assert _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0) == []


def test_baseline_excludes_the_current_run(client, db_session, user_a, agent_a):
    """The spike must be judged against earlier runs only, not against itself."""
    _insert_runs(db_session, agent_a["id"], NORMAL + [9000])
    spike = _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0)[0]
    assert spike["baseline_mean_ms"] < 1100  # the 9000 ms run is not part of its own baseline


def test_flat_baseline_break_is_flagged_even_though_z_is_undefined(client, db_session, user_a, agent_a):
    runs = _insert_runs(db_session, agent_a["id"], [1000] * 6 + [1500])
    flagged = _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0)
    assert [f["run_id"] for f in flagged] == [runs[-1].id]
    assert flagged[0]["detection_reason"] == "flat_baseline"
    assert flagged[0]["z_score"] is None


def test_small_baselines_are_never_judged(client, db_session, user_a, agent_a):
    """Fewer than 5 prior runs is too little evidence, so nothing is flagged."""
    _insert_runs(db_session, agent_a["id"], [1000, 1000, 1000, 1000, 50000])
    assert _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0) == []


def test_failed_and_running_runs_are_excluded(client, db_session, user_a, agent_a):
    _insert_runs(db_session, agent_a["id"], NORMAL)
    _insert_runs(db_session, agent_a["id"], [90000], status="failed", start_offset_min=200)
    _insert_runs(db_session, agent_a["id"], [90000], status="running", start_offset_min=260)
    assert _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0) == []


def test_threshold_controls_sensitivity(client, db_session, user_a, agent_a):
    _insert_runs(db_session, agent_a["id"], NORMAL + [1400])
    assert _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=3.0) != []
    # 100 is the API's maximum threshold; the spike (z ~ 30+) must then pass unflagged.
    assert _anomalies(client, user_a, agent_id=agent_a["id"], z_threshold=100.0) == []


def test_since_filter_limits_the_window(client, db_session, user_a, agent_a):
    _insert_runs(db_session, agent_a["id"], NORMAL + [9000])
    later = (BASE_TIME + timedelta(days=1)).isoformat()
    assert _anomalies(client, user_a, agent_id=agent_a["id"], since=later) == []


def test_other_users_anomalies_are_invisible(client, db_session, user_a, user_b, agent_a):
    _insert_runs(db_session, agent_a["id"], NORMAL + [9000])
    assert _anomalies(client, user_b) == []


def test_agent_filter_must_be_owned(client, db_session, user_a, user_b, agent_a):
    response = client.get(
        "/api/v1/analytics/latency-anomalies",
        headers=_auth(user_b),
        params={"agent_id": agent_a["id"]},
    )
    assert response.status_code == 404


def test_invalid_threshold_is_rejected(client, user_a):
    response = client.get("/api/v1/analytics/latency-anomalies", headers=_auth(user_a), params={"z_threshold": 0})
    assert response.status_code == 422
