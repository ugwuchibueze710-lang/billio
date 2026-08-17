def test_submit_feedback_requires_auth(client):
    resp = client.post("/api/feedback", json={"type": "bug", "message": "Something broke"})
    assert resp.status_code == 401


def test_submit_feedback_success(client, auth_headers):
    headers, _ = auth_headers(username="fbok")
    resp = client.post("/api/feedback", headers=headers, json={"type": "review", "message": "Love it", "rating": 5})
    assert resp.status_code == 201
    body = resp.get_json()["feedback"]
    assert body["type"] == "review"
    assert body["rating"] == 5
    assert body["status"] == "new"
    assert "admin_note" not in body
    assert "user_id" not in body


def test_submit_feedback_rejects_invalid_type(client, auth_headers):
    headers, _ = auth_headers(username="fbbadtype")
    resp = client.post("/api/feedback", headers=headers, json={"type": "not_a_real_type", "message": "hi"})
    assert resp.status_code == 422


def test_submit_feedback_rejects_empty_message(client, auth_headers):
    headers, _ = auth_headers(username="fbempty")
    resp = client.post("/api/feedback", headers=headers, json={"type": "bug", "message": ""})
    assert resp.status_code == 422


def test_submit_feedback_rejects_oversized_message(client, auth_headers):
    headers, _ = auth_headers(username="fboversize")
    resp = client.post("/api/feedback", headers=headers, json={"type": "bug", "message": "x" * 6000})
    assert resp.status_code == 422


def test_submit_feedback_rejects_rating_out_of_range(client, auth_headers):
    headers, _ = auth_headers(username="fbrating")
    resp = client.post("/api/feedback", headers=headers, json={"type": "review", "message": "ok", "rating": 7})
    assert resp.status_code == 422


def test_feedback_rate_limited(client, auth_headers, app):
    headers, _ = auth_headers(username="fbratelimit")
    limit = int(app.config["FEEDBACK_RATE_LIMIT"].split(" per")[0])
    statuses = []
    for i in range(limit + 2):
        resp = client.post("/api/feedback", headers=headers, json={"type": "other", "message": f"msg {i}"})
        statuses.append(resp.status_code)
    assert 429 in statuses


def test_admin_note_never_exposed_to_normal_user(client, auth_headers):
    headers, _ = auth_headers(username="fbusernote")
    admin_headers, _ = auth_headers(username="fbadminnote", is_admin=True)

    resp = client.post("/api/feedback", headers=headers, json={"type": "bug", "message": "bug report"})
    feedback_id = resp.get_json()["feedback"]["id"]

    client.patch(
        f"/api/admin/feedback/{feedback_id}",
        headers=admin_headers,
        json={"admin_note": "Internal: likely recurrence bug"},
    )

    user_view = client.get(f"/api/feedback/{feedback_id}", headers=headers).get_json()["feedback"]
    assert "admin_note" not in user_view

    my_list = client.get("/api/feedback", headers=headers).get_json()["feedback"]
    assert all("admin_note" not in f for f in my_list)


def test_admin_can_change_status_and_it_is_logged(client, auth_headers, app):
    headers, _ = auth_headers(username="fbstatususer")
    admin_headers, admin_id = auth_headers(username="fbstatusadmin", is_admin=True)

    resp = client.post("/api/feedback", headers=headers, json={"type": "improvement", "message": "please add x"})
    feedback_id = resp.get_json()["feedback"]["id"]

    update = client.patch(f"/api/admin/feedback/{feedback_id}", headers=admin_headers, json={"status": "reviewing"})
    assert update.status_code == 200
    assert update.get_json()["feedback"]["status"] == "reviewing"

    from app.models import AdminAuditLog
    from app.extensions import db

    with app.app_context():
        logs = AdminAuditLog.query.filter_by(action="feedback.updated").all()
        assert len(logs) >= 1
        assert logs[-1].metadata_json.get("new_status") == "reviewing"


def test_admin_feedback_list_shows_short_account_id_not_full_pii(client, auth_headers):
    headers, _ = auth_headers(username="fbpiiuser")
    admin_headers, _ = auth_headers(username="fbpiiadmin", is_admin=True)
    client.post("/api/feedback", headers=headers, json={"type": "other", "message": "hi"})

    listing = client.get("/api/admin/feedback", headers=admin_headers).get_json()["feedback"]
    assert len(listing) >= 1
    for item in listing:
        assert item["user_id"].startswith("user_")
        assert len(item["user_id"]) == len("user_") + 8
