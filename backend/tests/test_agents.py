"""Agent management: CRUD, validation, and per-user isolation."""


def _create(client, headers, **overrides):
    body = {"name": "Helper", "model": "gpt-4o", "environment": "staging"}
    body.update(overrides)
    return client.post("/api/v1/agents", headers=headers, json=body)


def test_create_agent_assigns_current_user_as_owner(client, user_a):
    response = _create(client, {"Authorization": user_a["Authorization"]})
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user_a["user_id"]
    assert body["status"] == "active"
    assert body["version"] == "1.0.0"


def test_create_agent_rejects_status_outside_database_check(client, user_a):
    # The database CHECK allows only active / inactive / maintenance.
    response = _create(client, {"Authorization": user_a["Authorization"]}, status="paused")
    assert response.status_code == 422


def test_create_agent_rejects_unknown_environment(client, user_a):
    response = _create(client, {"Authorization": user_a["Authorization"]}, environment="qa")
    assert response.status_code == 422


def test_list_agents_only_returns_own_agents(client, user_a, user_b):
    _create(client, {"Authorization": user_a["Authorization"]}, name="Mine")
    _create(client, {"Authorization": user_b["Authorization"]}, name="Theirs")
    response = client.get("/api/v1/agents", headers={"Authorization": user_a["Authorization"]})
    assert response.status_code == 200
    assert [a["name"] for a in response.json()] == ["Mine"]


def test_other_users_agent_is_reported_as_not_found(client, user_a, user_b, agent_a):
    response = client.get(f"/api/v1/agents/{agent_a['id']}", headers={"Authorization": user_b["Authorization"]})
    assert response.status_code == 404


def test_patch_updates_only_provided_fields(client, user_a, agent_a):
    response = client.patch(
        f"/api/v1/agents/{agent_a['id']}",
        headers={"Authorization": user_a["Authorization"]},
        json={"status": "maintenance"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "maintenance"
    assert body["name"] == agent_a["name"]


def test_delete_agent_without_history_returns_204(client, user_a, agent_a):
    response = client.delete(f"/api/v1/agents/{agent_a['id']}", headers={"Authorization": user_a["Authorization"]})
    assert response.status_code == 204


def test_delete_agent_with_runs_is_blocked_with_409(client, user_a, agent_a):
    headers = {"Authorization": user_a["Authorization"]}
    run = client.post("/api/v1/runs", headers=headers, json={"agent_id": agent_a["id"]})
    assert run.status_code == 201, run.text
    response = client.delete(f"/api/v1/agents/{agent_a['id']}", headers=headers)
    assert response.status_code == 409
    # The agent must still exist after the refused delete.
    assert client.get(f"/api/v1/agents/{agent_a['id']}", headers=headers).status_code == 200


def test_agent_name_is_required(client, user_a):
    response = _create(client, {"Authorization": user_a["Authorization"]}, name="   ")
    assert response.status_code == 422
