"""Novelty 7: multi-agent trace trees and subtree cost roll-up."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.metric import Metric
from app.models.run import Run


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _run(client, user, agent_id, parent=None):
    body = {"agent_id": agent_id}
    if parent is not None:
        body["parent_run_id"] = parent["id"]
    response = client.post("/api/v1/runs", headers=_auth(user), json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def tree(client, user_a, agent_a):
    """root -> (child_1 -> grandchild), child_2"""
    root = _run(client, user_a, agent_a["id"])
    child_1 = _run(client, user_a, agent_a["id"], parent=root)
    grandchild = _run(client, user_a, agent_a["id"], parent=child_1)
    child_2 = _run(client, user_a, agent_a["id"], parent=root)
    return {"root": root, "child_1": child_1, "grandchild": grandchild, "child_2": child_2}


def test_trace_is_depth_first_with_correct_depths(client, user_a, tree):
    rows = client.get(f"/api/v1/runs/{tree['root']['id']}/trace", headers=_auth(user_a)).json()
    order = [(r["run_id"], r["depth"]) for r in rows]
    assert order == [
        (tree["root"]["id"], 0),
        (tree["child_1"]["id"], 1),
        (tree["grandchild"]["id"], 2),
        (tree["child_2"]["id"], 1),
    ]
    assert rows[1]["parent_run_id"] == tree["root"]["id"]


def test_trace_of_a_sub_run_returns_only_its_subtree(client, user_a, tree):
    rows = client.get(f"/api/v1/runs/{tree['child_1']['id']}/trace", headers=_auth(user_a)).json()
    assert [r["run_id"] for r in rows] == [tree["child_1"]["id"], tree["grandchild"]["id"]]


def test_trace_of_a_run_with_no_children_is_just_that_run(client, user_a, tree):
    rows = client.get(f"/api/v1/runs/{tree['grandchild']['id']}/trace", headers=_auth(user_a)).json()
    assert len(rows) == 1 and rows[0]["depth"] == 0


def test_trace_of_another_users_run_is_not_found(client, user_a, user_b, tree):
    response = client.get(f"/api/v1/runs/{tree['root']['id']}/trace", headers=_auth(user_b))
    assert response.status_code == 404


def test_parent_must_be_one_of_the_callers_runs(client, user_a, user_b, agent_a):
    bob_agent = client.post("/api/v1/agents", headers=_auth(user_b), json={"name": "Bob", "model": "m"}).json()
    bob_run = _run(client, user_b, bob_agent["id"])
    response = client.post(
        "/api/v1/runs",
        headers=_auth(user_a),
        json={"agent_id": agent_a["id"], "parent_run_id": bob_run["id"]},
    )
    assert response.status_code == 404


def test_parent_link_cannot_be_changed_after_creation(db_session, tree):
    with pytest.raises(Exception, match="parent_run_id is immutable"):
        db_session.execute(
            text("UPDATE runs SET parent_run_id = NULL WHERE id = :id"),
            {"id": tree["grandchild"]["id"]},
        )
        db_session.commit()
    db_session.rollback()


def test_database_rejects_a_cross_owner_parent_even_without_the_api(db_session, client, user_a, user_b, agent_a):
    bob_agent = client.post("/api/v1/agents", headers={"Authorization": user_b["Authorization"]}, json={"name": "Bob", "model": "m"}).json()
    bob_run = Run(agent_id=bob_agent["id"], status="running", started_at=datetime(2026, 3, 1, 9, 0, 0))
    db_session.add(bob_run)
    db_session.commit()
    with pytest.raises(Exception, match="same owner"):
        db_session.add(Run(agent_id=agent_a["id"], status="running", parent_run_id=bob_run.id))
        db_session.commit()
    db_session.rollback()


def _price(db_session, model, input_per_1k, output_per_1k):
    db_session.execute(
        text(
            "INSERT INTO model_pricing (model, effective_from, input_usd_per_1k, output_usd_per_1k) "
            "VALUES (:m, '2026-01-01', :i, :o)"
        ),
        {"m": model, "i": input_per_1k, "o": output_per_1k},
    )
    db_session.commit()


def test_subtree_cost_rolls_up_every_descendant(client, db_session, user_a, agent_a, tree):
    _price(db_session, "gpt-4o", 0.01, 0.01)
    for run, tokens in ((tree["root"], 1000), (tree["grandchild"], 2000)):
        db_session.add_all(
            [
                Metric(run_id=run["id"], metric_name="input_tokens", metric_value=tokens, unit="tokens"),
                Metric(run_id=run["id"], metric_name="output_tokens", metric_value=0, unit="tokens"),
            ]
        )
    db_session.commit()

    body = client.get(f"/api/v1/runs/{tree['root']['id']}/subtree-cost", headers=_auth(user_a)).json()
    assert body["runs_in_tree"] == 4
    assert body["subtree_cost_usd"] == pytest.approx(0.01 * 1 + 0.01 * 2)
    assert body["unpriced_runs"] == 0
    assert body["attribution_method"] == "rollup"


def test_subtree_cost_without_usage_is_zero_not_guessed(client, db_session, user_a, agent_a, tree):
    response = client.get(f"/api/v1/runs/{tree['child_1']['id']}/subtree-cost", headers=_auth(user_a))
    body = response.json()
    assert body["runs_in_tree"] == 2
    assert body["subtree_cost_usd"] == 0
    assert body["unpriced_runs"] == 0  # runs with no usage are not "unpriced"; they have no usage at all


def test_subtree_cost_of_another_users_run_is_not_found(client, user_b, tree):
    response = client.get(f"/api/v1/runs/{tree['root']['id']}/subtree-cost", headers=_auth(user_b))
    assert response.status_code == 404
