"""Task and run management: ownership, composite FK rules, and run completion."""


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _task(client, user, agent_id, title="Summarize backlog"):
    return client.post(
        "/api/v1/tasks",
        headers=_auth(user),
        json={"agent_id": agent_id, "title": title, "priority": "high"},
    )


def test_create_task_for_own_agent(client, user_a, agent_a):
    response = _task(client, user_a, agent_a["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["agent_id"] == agent_a["id"]
    assert body["status"] == "pending"
    assert body["priority"] == "high"


def test_create_task_for_another_users_agent_is_not_found(client, user_b, agent_a):
    response = _task(client, user_b, agent_a["id"])
    assert response.status_code == 404


def test_task_list_is_scoped_to_owner(client, user_a, user_b, agent_a):
    _task(client, user_a, agent_a["id"], title="Mine")
    response = client.get("/api/v1/tasks", headers=_auth(user_b))
    assert response.status_code == 200
    assert response.json() == []


def test_create_standalone_run_defaults_to_running(client, user_a, agent_a):
    response = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "running"
    assert body["task_id"] is None
    assert body["completed_at"] is None


def test_run_with_task_of_same_agent_is_accepted(client, user_a, agent_a):
    task = _task(client, user_a, agent_a["id"]).json()
    response = client.post(
        "/api/v1/runs",
        headers=_auth(user_a),
        json={"agent_id": agent_a["id"], "task_id": task["id"]},
    )
    assert response.status_code == 201
    assert response.json()["task_id"] == task["id"]


def test_run_with_task_of_different_agent_is_rejected(client, user_a, agent_a):
    other_agent = client.post(
        "/api/v1/agents", headers=_auth(user_a), json={"name": "Other", "model": "claude"}
    ).json()
    task_on_other = _task(client, user_a, other_agent["id"]).json()
    response = client.post(
        "/api/v1/runs",
        headers=_auth(user_a),
        json={"agent_id": agent_a["id"], "task_id": task_on_other["id"]},
    )
    assert response.status_code == 400


def test_completing_a_run_sets_completed_at(client, user_a, agent_a):
    run = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]}).json()
    response = client.patch(
        f"/api/v1/runs/{run['id']}",
        headers=_auth(user_a),
        json={"status": "completed", "execution_time_ms": 842},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["execution_time_ms"] == 842
    assert body["completed_at"] is not None


def test_other_users_run_is_not_found(client, user_a, user_b, agent_a):
    run = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]}).json()
    assert client.get(f"/api/v1/runs/{run['id']}", headers=_auth(user_b)).status_code == 404
    assert (
        client.patch(f"/api/v1/runs/{run['id']}", headers=_auth(user_b), json={"status": "failed"}).status_code
        == 404
    )


def test_run_rejects_status_outside_check_constraint(client, user_a, agent_a):
    response = client.post(
        "/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"], "status": "paused"}
    )
    assert response.status_code == 422
