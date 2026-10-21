"""Novelty 9: monthly partitioning, integrity triggers that replace foreign keys, and retention.

Order matters inside this module: the placement checks run first, and the retention test
(which drops the p_past partition) runs last.
"""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.run import Run


@pytest.fixture()
def run_id(db_session, agent_a):
    run = Run(agent_id=agent_a["id"], status="running", started_at=datetime(2026, 10, 1, 9, 0, 0))
    db_session.add(run)
    db_session.commit()
    return run.id


def _insert_log(db_session, run_id, agent_id, timestamp, message="m"):
    db_session.execute(
        text(
            "INSERT INTO logs (run_id, agent_id, severity, message, timestamp) "
            "VALUES (:r, :a, 'INFO', :m, :t)"
        ),
        {"r": run_id, "a": agent_id, "m": message, "t": timestamp},
    )
    db_session.commit()


def _count_in_partition(db_session, table, partition):
    return db_session.execute(text(f"SELECT COUNT(*) FROM {table} PARTITION ({partition})")).scalar()


# ---------------------------------------------------------------- placement

def test_log_is_stored_in_the_partition_for_its_month(db_session, agent_a, run_id):
    _insert_log(db_session, run_id, agent_a["id"], datetime(2026, 10, 5, 12, 0, 0))
    assert _count_in_partition(db_session, "logs", "p202610") == 1


def test_event_is_stored_in_the_partition_for_its_month(db_session, run_id):
    db_session.execute(
        text("INSERT INTO events (run_id, event_type, event_name, timestamp) VALUES (:r, 'tool', 'x', '2026-10-06 08:00:00')"),
        {"r": run_id},
    )
    db_session.commit()
    assert _count_in_partition(db_session, "events", "p202610") == 1


def test_dates_before_2026_fall_into_the_past_partition(db_session, agent_a, run_id):
    _insert_log(db_session, run_id, agent_a["id"], datetime(2025, 12, 5, 10, 0, 0), message="old")
    assert _count_in_partition(db_session, "logs", "p_past") == 1


# ---------------------------------------------------------------- integrity (replaces foreign keys)

def test_log_must_reference_an_existing_run(db_session, agent_a):
    with pytest.raises(Exception, match="does not reference an existing run"):
        _insert_log(db_session, 999999, agent_a["id"], datetime(2026, 10, 5, 12, 0, 0))
    db_session.rollback()


def test_log_agent_must_match_its_run_agent(db_session, client, user_a, agent_a, run_id):
    other = client.post("/api/v1/agents", headers={"Authorization": user_a["Authorization"]}, json={"name": "Other", "model": "m"}).json()
    with pytest.raises(Exception, match="must match the agent of its run"):
        _insert_log(db_session, run_id, other["id"], datetime(2026, 10, 5, 12, 0, 0))
    db_session.rollback()


def test_event_must_reference_an_existing_run(db_session):
    with pytest.raises(Exception, match="does not reference an existing run"):
        db_session.execute(text("INSERT INTO events (run_id, event_type, event_name) VALUES (999999, 't', 'n')"))
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------- maintenance

def test_ensure_month_partition_is_idempotent(db_session):
    db_session.execute(text("CALL sp_ensure_month_partition('logs', '2026-10-01')"))
    db_session.execute(text("CALL sp_ensure_month_partition('logs', '2026-10-01')"))
    db_session.commit()
    count = db_session.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.partitions "
            "WHERE table_schema = DATABASE() AND table_name = 'logs' AND partition_name = 'p202610'"
        )
    ).scalar()
    assert count == 1


def test_partition_maintenance_only_accepts_logs_and_events(db_session):
    with pytest.raises(Exception, match="limited to logs and events"):
        db_session.execute(text("CALL sp_ensure_month_partition('users', '2026-10-01')"))
        db_session.commit()
    db_session.rollback()


def test_maintenance_event_is_scheduled_and_procedure_runs(db_session):
    scheduled = db_session.execute(
        text("SELECT COUNT(*) FROM information_schema.events WHERE event_schema = DATABASE() AND event_name = 'ev_partition_maintenance'")
    ).scalar()
    assert scheduled == 1
    db_session.execute(text("CALL sp_maintain_partitions()"))
    db_session.commit()


# ---------------------------------------------------------------- retention (runs last)

def test_retention_drops_only_whole_old_partitions(db_session, agent_a, run_id):
    _insert_log(db_session, run_id, agent_a["id"], datetime(2025, 11, 15, 10, 0, 0), message="ancient")
    _insert_log(db_session, run_id, agent_a["id"], datetime(2026, 10, 15, 10, 0, 0), message="recent")

    db_session.execute(text("SET @dropped = NULL"))
    db_session.execute(text("CALL sp_drop_partitions_before('logs', '2026-01-01', @dropped)"))
    dropped = db_session.execute(text("SELECT @dropped")).scalar()
    db_session.commit()

    assert dropped == 1
    remaining = db_session.execute(text("SELECT message FROM logs")).scalars().all()
    assert remaining == ["recent"]


def test_retention_refuses_tables_outside_the_whitelist(db_session):
    with pytest.raises(Exception, match="limited to logs and events"):
        db_session.execute(text("CALL sp_drop_partitions_before('users', '2026-01-01', @dropped)"))
        db_session.commit()
    db_session.rollback()
