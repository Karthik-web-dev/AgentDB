"""Novelty 12: query plans are verified with EXPLAIN, not assumed.

Each test asserts the index or partition the optimiser must choose for a query the
application actually runs. If a schema or index change silently breaks the plan, the
test fails. docs/query-plans.md records the same plans with explanations.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.models.run import Run


@pytest.fixture()
def dataset(db_session, agent_a):
    """A run per day in October 2026, each with several logs and one event: enough rows for real plans."""
    runs = []
    for day in range(1, 29):
        run = Run(agent_id=agent_a["id"], status="completed", started_at=datetime(2026, 10, day, 9, 0, 0), execution_time_ms=100 + day)
        db_session.add(run)
        runs.append(run)
    db_session.commit()

    severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    for i in range(400):
        run = runs[i % len(runs)]
        db_session.execute(
            text(
                "INSERT INTO logs (run_id, agent_id, severity, message, timestamp) "
                "VALUES (:r, :a, :s, 'bulk', :t)"
            ),
            {
                "r": run.id,
                "a": agent_a["id"],
                "s": severities[i % len(severities)],
                "t": datetime(2026, 10, 1 + (i % 28), 6, 0, 0) + timedelta(minutes=i),
            },
        )
    db_session.execute(
        text("INSERT INTO events (run_id, event_type, event_name, timestamp) VALUES (:r, 'tool', 'search', NOW())"),
        {"r": runs[0].id},
    )
    db_session.commit()

    db_session.execute(text("CALL sp_refresh_hourly_stats('2026-10-01 00:00:00')"))
    db_session.commit()
    for table in ("logs", "events", "agent_hourly_stats"):
        db_session.execute(text(f"ANALYZE TABLE {table}"))
    db_session.commit()
    return {"agent_id": agent_a["id"], "run_id": runs[0].id}


def _plan(db_session, sql, params=None):
    rows = db_session.execute(text("EXPLAIN " + sql), params or {}).mappings().all()
    return [dict(r) for r in rows]


def test_log_search_by_severity_and_time_uses_the_composite_index(db_session, dataset):
    plan = _plan(
        db_session,
        "SELECT id FROM logs WHERE severity = 'ERROR' AND timestamp >= '2026-10-05' AND timestamp < '2026-10-10'",
    )
    assert plan[0]["key"] == "idx_logs_severity_timestamp"


def test_time_range_query_touches_only_the_matching_month_partition(db_session, dataset):
    """Partition pruning: a one-week query must not read the other months."""
    plan = _plan(
        db_session,
        "SELECT COUNT(*) FROM logs WHERE timestamp >= '2026-10-05' AND timestamp < '2026-10-12'",
    )
    assert plan[0]["partitions"] == "p202610"


def test_events_for_one_run_use_the_run_index(db_session, dataset):
    plan = _plan(db_session, "SELECT id FROM events WHERE run_id = :r", {"r": dataset["run_id"]})
    assert plan[0]["key"] == "idx_events_run_id"


def test_hourly_rollup_range_uses_the_primary_key(db_session, dataset):
    plan = _plan(
        db_session,
        "SELECT * FROM agent_hourly_stats WHERE agent_id = :a AND bucket_start >= '2026-10-05 00:00:00'",
        {"a": dataset["agent_id"]},
    )
    assert plan[0]["key"] == "PRIMARY"


def test_ownership_join_uses_the_agent_index_on_runs(db_session, dataset):
    plan = _plan(db_session, "SELECT COUNT(*) FROM runs WHERE agent_id = :a AND status = 'failed'", {"a": dataset["agent_id"]})
    assert plan[0]["key"] in ("idx_runs_agent_id_status", "fk_runs_agent")
