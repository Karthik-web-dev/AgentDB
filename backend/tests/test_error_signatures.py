"""Novelty 8: error signatures (normalised, de-duplicated failure messages)."""

from sqlalchemy import text


def _auth(user):
    return {"Authorization": user["Authorization"]}


def _failed_run(client, user, agent_id, message):
    response = client.post(
        "/api/v1/runs",
        headers=_auth(user),
        json={"agent_id": agent_id, "status": "failed", "error_message": message},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _signatures(client, user):
    response = client.get("/api/v1/errors/signatures", headers=_auth(user))
    assert response.status_code == 200, response.text
    return response.json()


def test_numbers_are_normalised_so_similar_errors_share_one_signature(client, user_a, agent_a):
    first = _failed_run(client, user_a, agent_a["id"], "Rate limit exceeded for 1200 tokens")
    second = _failed_run(client, user_a, agent_a["id"], "Rate limit exceeded for 980 tokens")
    assert first["error_signature_id"] == second["error_signature_id"]

    (signature,) = _signatures(client, user_a)
    assert signature["occurrences"] == 2
    assert signature["normalized_message"] == "rate limit exceeded for # tokens"


def test_case_and_whitespace_do_not_create_new_signatures(client, user_a, agent_a):
    a = _failed_run(client, user_a, agent_a["id"], "Timeout   talking to provider")
    b = _failed_run(client, user_a, agent_a["id"], "  TIMEOUT talking to provider ")
    assert a["error_signature_id"] == b["error_signature_id"]


def test_different_messages_get_different_signatures(client, user_a, agent_a):
    a = _failed_run(client, user_a, agent_a["id"], "Rate limit exceeded")
    b = _failed_run(client, user_a, agent_a["id"], "JSON schema validation failed")
    assert a["error_signature_id"] != b["error_signature_id"]
    assert len(_signatures(client, user_a)) == 2


def test_run_without_error_has_no_signature(client, user_a, agent_a):
    run = client.post("/api/v1/runs", headers=_auth(user_a), json={"agent_id": agent_a["id"]}).json()
    assert run["error_signature_id"] is None


def test_same_text_written_by_two_users_stays_separate(client, user_a, user_b, agent_a):
    bob_agent = client.post("/api/v1/agents", headers=_auth(user_b), json={"name": "Bob", "model": "m"}).json()
    a = _failed_run(client, user_a, agent_a["id"], "Connection reset by peer")
    b = _failed_run(client, user_b, bob_agent["id"], "Connection reset by peer")
    assert a["error_signature_id"] != b["error_signature_id"]
    assert len(_signatures(client, user_a)) == 1
    assert len(_signatures(client, user_b)) == 1


def test_changing_the_error_message_moves_the_run_to_a_new_signature(client, user_a, agent_a):
    run = _failed_run(client, user_a, agent_a["id"], "Timeout after 30 seconds")
    updated = client.patch(
        f"/api/v1/runs/{run['id']}",
        headers=_auth(user_a),
        json={"error_message": "Schema mismatch on field 7"},
    ).json()
    assert updated["error_signature_id"] != run["error_signature_id"]


def test_runs_listed_under_a_signature(client, user_a, agent_a):
    first = _failed_run(client, user_a, agent_a["id"], "Rate limit exceeded for 1 tokens")
    second = _failed_run(client, user_a, agent_a["id"], "Rate limit exceeded for 2 tokens")
    (signature,) = _signatures(client, user_a)
    runs = client.get(f"/api/v1/errors/signatures/{signature['id']}/runs", headers=_auth(user_a)).json()
    assert [r["id"] for r in runs] == [second["id"], first["id"]]


def test_signature_of_another_user_is_not_found(client, user_a, user_b, agent_a):
    _failed_run(client, user_a, agent_a["id"], "Private failure text")
    (signature,) = _signatures(client, user_a)
    response = client.get(f"/api/v1/errors/signatures/{signature['id']}/runs", headers=_auth(user_b))
    assert response.status_code == 404
    assert _signatures(client, user_b) == []


def test_signatures_are_ordered_by_frequency(client, user_a, agent_a):
    _failed_run(client, user_a, agent_a["id"], "Rare failure")
    for _ in range(3):
        _failed_run(client, user_a, agent_a["id"], "Common failure")
    ranked = _signatures(client, user_a)
    assert ranked[0]["normalized_message"] == "common failure"
    assert ranked[0]["occurrences"] == 3


def test_database_maintains_counts_even_without_the_api(db_session, client, user_a, agent_a):
    db_session.execute(
        text("INSERT INTO runs (agent_id, status, started_at, error_message) VALUES (:a, 'failed', NOW(), 'Raw insert 42')"),
        {"a": agent_a["id"]},
    )
    db_session.commit()
    (signature,) = _signatures(client, user_a)
    assert signature["normalized_message"] == "raw insert #"
    assert signature["occurrences"] == 1
