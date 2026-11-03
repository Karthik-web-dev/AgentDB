"""Novelty 10: incrementally refreshed hourly rollups and the overview endpoint."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.run import Run


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _seed_runs(db_session, agent_id):
    """Ten runs across two hours. Latencies on completed runs: 100, 200, 400, 1000."""
    rows = [
        ("completed", datetime(2026, 10, 1, 10, 5), 100),
        ("completed", datetime(2026, 10, 1, 10, 30), 200),
        ("completed", datetime(2026, 10, 1, 10, 50), 400),
        ("failed", datetime(2026, 10, 1, 10, 59), None),
        ("completed", datetime(2026, 10, 1, 11, 10), 1000),
    ]
    runs = [
        Run(agent_id=agent_id, status=status, started_at=started, completed_at=started, execution_time_ms=latency)
        for status, started, latency in rows
    ]
    db_session.add_all(runs)
    db_session.commit()
    return runs


def _refresh(db_session, since="2026-10-01 10:00:00"):
    db_session.execute(text("CALL sp_refresh_hourly_stats(:s)"), {"s": since})
    db_session.commit()


def _bucket(db_session, agent_id, bucket):
    row = db_session.execute(
        text(
            "SELECT runs_total, runs_completed, runs_failed, latency_sum_ms, latency_count, max_latency_ms "
            "FROM agent_hourly_stats WHERE agent_id = :a AND bucket_start = :b"
        ),
        {"a": agent_id, "b": bucket},
    ).mappings().one()
    return dict(row)


def test_refresh_aggregates_each_hour_exactly(db_session, agent_a):
    _seed_runs(db_session, agent_a["id"])
    _refresh(db_session)

    ten = _bucket(db_session, agent_a["id"], datetime(2026, 10, 1, 10, 0, 0))
    assert ten == {
        "runs_total": 4,
        "runs_completed": 3,
        "runs_failed": 1,
        "latency_sum_ms": 700,
        "latency_count": 3,
        "max_latency_ms": 400,
    }
    eleven = _bucket(db_session, agent_a["id"], datetime(2026, 10, 1, 11, 0, 0))
    assert eleven["runs_total"] == 1 and eleven["latency_sum_ms"] == 1000


def test_refresh_is_idempotent(db_session, agent_a):
    _seed_runs(db_session, agent_a["id"])
    _refresh(db_session)
    first = _bucket(db_session, agent_a["id"], datetime(2026, 10, 1, 10, 0, 0))
    _refresh(db_session)
    _refresh(db_session)
    assert _bucket(db_session, agent_a["id"], datetime(2026, 10, 1, 10, 0, 0)) == first


def test_refresh_picks_up_runs_that_changed_status_later(db_session, agent_a):
    runs = _seed_runs(db_session, agent_a["id"])
    _refresh(db_session)
    failed = runs[3]
    failed.status = "completed"
    failed.execution_time_ms = 50
    db_session.commit()
    _refresh(db_session)
    ten = _bucket(db_session, agent_a["id"], datetime(2026, 10, 1, 10, 0, 0))
    assert ten["runs_failed"] == 0
    assert ten["runs_completed"] == 4
    assert ten["latency_sum_ms"] == 750


def test_refresh_ignores_hours_before_the_requested_start(db_session, agent_a):
    _seed_runs(db_session, agent_a["id"])
    _refresh(db_session, since="2026-10-01 11:00:00")
    buckets = db_session.execute(text("SELECT bucket_start FROM agent_hourly_stats")).scalars().all()
    assert buckets == [datetime(2026, 10, 1, 11, 0, 0)]


def test_hourly_bucket_must_be_on_the_hour(db_session, agent_a):
    with pytest.raises(Exception):
        db_session.execute(
            text(
                "INSERT INTO agent_hourly_stats (agent_id, bucket_start, runs_total, runs_completed, runs_failed, refreshed_at) "
                "VALUES (:a, '2026-10-01 10:30:00', 0, 0, 0, NOW())"
            ),
            {"a": agent_a["id"]},
        )
        db_session.commit()
    db_session.rollback()


def test_overview_reports_exact_totals_failure_rate_and_latency(client, db_session, user_a, agent_a):
    _seed_runs(db_session, agent_a["id"])
    response = client.get(
        "/api/v1/analytics/overview",
        headers=_auth(user_a),
        params={"since": "2026-10-01T10:00:00", "until": "2026-10-01T12:00:00"},
    )
    assert response.status_code == 200, response.text
    (row,) = response.json()
    assert row["agent_id"] == agent_a["id"]
    assert row["runs_total"] == 5
    assert row["runs_completed"] == 4
    assert row["runs_failed"] == 1
    assert row["failure_rate_pct"] == 20.0
    assert row["avg_latency_ms"] == pytest.approx(425.0)  # (100 + 200 + 400 + 1000) / 4
    assert row["max_latency_ms"] == 1000


def test_overview_refreshes_the_requested_range_on_read(client, db_session, user_a, agent_a):
    """No scheduled refresh has run here, yet the overview is still exact."""
    _seed_runs(db_session, agent_a["id"])
    count = db_session.execute(text("SELECT COUNT(*) FROM agent_hourly_stats")).scalar()
    assert count == 0
    client.get(
        "/api/v1/analytics/overview",
        headers=_auth(user_a),
        params={"since": "2026-10-01T10:00:00", "until": "2026-10-01T12:00:00"},
    )
    db_session.rollback()  # end the earlier read transaction so the recount sees the API's writes
    assert db_session.execute(text("SELECT COUNT(*) FROM agent_hourly_stats")).scalar() == 2


def test_overview_is_invisible_to_other_users(client, db_session, user_a, user_b, agent_a):
    _seed_runs(db_session, agent_a["id"])
    response = client.get(
        "/api/v1/analytics/overview",
        headers=_auth(user_b),
        params={"since": "2026-10-01T10:00:00", "until": "2026-10-01T12:00:00"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_hourly_refresh_event_is_scheduled(db_session):
    count = db_session.execute(
        text("SELECT COUNT(*) FROM information_schema.events WHERE event_schema = DATABASE() AND event_name = 'ev_refresh_hourly_stats'")
    ).scalar()
    assert count == 1
