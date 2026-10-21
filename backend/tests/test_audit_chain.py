"""Novelty 1: tamper-evident audit chain (database-enforced hash chain)."""

import pytest
from sqlalchemy import text

CHAIN_TRIGGERS = {
    "trg_audit_logs_chain_before_insert": "BEFORE INSERT",
    "trg_audit_logs_chain_after_insert": "AFTER INSERT",
    "trg_audit_logs_no_update": "BEFORE UPDATE",
    "trg_audit_logs_no_delete": "BEFORE DELETE",
}


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _make_audit_rows(client, user, agent, count=2):
    """Each status change on an agent writes one row through trg_agents_after_update_audit."""
    statuses = ["maintenance", "active", "inactive", "active"]
    for i in range(count):
        response = client.patch(
            f"/api/v1/agents/{agent['id']}",
            headers=_auth(user),
            json={"status": statuses[i % len(statuses)]},
        )
        assert response.status_code == 200, response.text


def _trigger_definition(db_session, name):
    row = db_session.execute(text(f"SHOW CREATE TRIGGER {name}")).mappings().one()
    return row["SQL Original Statement"]


def _drop_trigger(db_session, name):
    db_session.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
    db_session.commit()


def _restore(db_session, definitions):
    for statement in definitions:
        db_session.execute(text(statement))
    db_session.commit()


def test_status_change_writes_chained_audit_row(client, db_session, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=1)
    rows = client.get("/api/v1/audit", headers=_auth(user_a)).json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["action"] == "UPDATE_AGENT_CONFIG"
    assert row["chain_seq"] is not None
    assert len(row["row_hash"]) == 64
    assert len(row["prev_hash"]) == 64


def test_chain_links_each_row_to_the_one_before(client, db_session, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=3)
    rows = db_session.execute(
        text("SELECT chain_seq, prev_hash, row_hash FROM audit_logs ORDER BY chain_seq")
    ).all()
    assert [r.chain_seq for r in rows] == list(range(1, len(rows) + 1))
    for earlier, later in zip(rows, rows[1:]):
        assert later.prev_hash == earlier.row_hash
    assert rows[0].prev_hash == "0" * 64


def test_verify_reports_intact_chain(client, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=3)
    response = client.get("/api/v1/audit/verify", headers=_auth(user_a))
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["rows_checked"] >= 3
    assert body["first_broken_seq"] is None


def test_chained_rows_cannot_be_updated(client, db_session, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=1)
    with pytest.raises(Exception, match="tamper-evident"):
        db_session.execute(text("UPDATE audit_logs SET action = 'FORGED' WHERE chain_seq = 1"))
        db_session.commit()
    db_session.rollback()


def test_chained_rows_cannot_be_deleted(client, db_session, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=1)
    with pytest.raises(Exception, match="append-only"):
        db_session.execute(text("DELETE FROM audit_logs WHERE chain_seq = 1"))
        db_session.commit()
    db_session.rollback()


def test_user_with_audit_history_cannot_be_deleted(client, db_session, user_a, agent_a):
    _make_audit_rows(client, user_a, agent_a, count=1)
    with pytest.raises(Exception):
        db_session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_a["user_id"]})
        db_session.commit()
    db_session.rollback()


def test_verifier_detects_forgery_once_the_trigger_is_bypassed(client, db_session, user_a, agent_a):
    """Simulate a privileged attacker who drops the guard, edits a row, and restores the guard."""
    _make_audit_rows(client, user_a, agent_a, count=3)
    guard = _trigger_definition(db_session, "trg_audit_logs_no_update")
    _drop_trigger(db_session, "trg_audit_logs_no_update")
    try:
        db_session.execute(text("UPDATE audit_logs SET details = JSON_OBJECT('forged', TRUE) WHERE chain_seq = 2"))
        db_session.commit()
        body = client.get("/api/v1/audit/verify", headers=_auth(user_a)).json()
        assert body["is_valid"] is False
        assert body["first_broken_seq"] == 2
        assert "BROKEN" in body["message"]
    finally:
        _restore(db_session, [guard])


def test_verifier_detects_a_removed_middle_row(client, db_session, user_a, agent_a):
    """A gap in the sequence (a deleted row) is reported at the first position after the gap."""
    _make_audit_rows(client, user_a, agent_a, count=3)
    guards = [_trigger_definition(db_session, n) for n in ("trg_audit_logs_no_delete",)]
    _drop_trigger(db_session, "trg_audit_logs_no_delete")
    try:
        db_session.execute(text("DELETE FROM audit_logs WHERE chain_seq = 2"))
        db_session.commit()
        body = client.get("/api/v1/audit/verify", headers=_auth(user_a)).json()
        assert body["is_valid"] is False
        assert body["first_broken_seq"] == 3
    finally:
        _restore(db_session, guards)


def test_backfill_chains_legacy_rows_and_refuses_to_run_twice(client, db_session, user_a, agent_a):
    """Legacy rows (inserted before the chain existed) can be chained once, in id order."""
    names = ["trg_audit_logs_chain_before_insert", "trg_audit_logs_chain_after_insert"]
    definitions = [_trigger_definition(db_session, n) for n in names]
    for n in names:
        _drop_trigger(db_session, n)
    try:
        for i in range(3):
            db_session.execute(
                text(
                    "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, timestamp) "
                    "VALUES (:u, 'LEGACY', 'agents', :e, NULL, '2026-09-01 10:00:00')"
                ),
                {"u": user_a["user_id"], "e": i + 1},
            )
        db_session.commit()
        db_session.execute(text("CALL sp_backfill_audit_chain()"))
        db_session.commit()
        verified = db_session.execute(text("SELECT COUNT(*) FROM audit_logs WHERE row_hash IS NOT NULL")).scalar()
        assert verified == 3
        with pytest.raises(Exception, match="already contains chained rows"):
            db_session.execute(text("CALL sp_backfill_audit_chain()"))
            db_session.commit()
        db_session.rollback()
    finally:
        _restore(db_session, definitions)

    db_session.execute(text("CALL sp_verify_audit_chain(@v, @n, @b)"))
    valid, checked, broken = db_session.execute(text("SELECT @v, @n, @b")).one()
    assert valid == 1 and checked == 3 and broken is None
