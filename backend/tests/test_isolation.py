"""
User A must never be able to read, modify, or delete User B's data through
ANY endpoint. This is the single most important security property of the
application; these tests exercise it across every resource type.
"""
from datetime import date


def _create_bill(client, headers):
    resp = client.post(
        "/api/bills",
        headers=headers,
        json={"name": "Private Bill", "amount": "42.00", "recurrence": "monthly", "due_date": date.today().isoformat()},
    )
    return resp.get_json()["bill"]


def test_bill_isolation(client, auth_headers):
    headers_a, _ = auth_headers(username="isoA1")
    headers_b, _ = auth_headers(username="isoB1")
    bill = _create_bill(client, headers_a)

    assert client.get(f"/api/bills/{bill['id']}", headers=headers_b).status_code == 404
    assert client.patch(f"/api/bills/{bill['id']}", headers=headers_b, json={"name": "hacked"}).status_code == 404
    assert client.delete(f"/api/bills/{bill['id']}", headers=headers_b).status_code == 404

    b_bills = client.get("/api/bills?status=all", headers=headers_b).get_json()["bills"]
    assert all(b["id"] != bill["id"] for b in b_bills)


def test_occurrence_isolation(client, auth_headers):
    headers_a, _ = auth_headers(username="isoA2")
    headers_b, _ = auth_headers(username="isoB2")
    _create_bill(client, headers_a)
    occ = client.get("/api/occurrences", headers=headers_a).get_json()["occurrences"][0]

    assert client.get(f"/api/occurrences/{occ['id']}", headers=headers_b).status_code == 404
    assert client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers_b).status_code == 404

    b_occs = client.get("/api/occurrences", headers=headers_b).get_json()["occurrences"]
    assert b_occs == []


def test_history_and_dashboard_isolation(client, auth_headers):
    headers_a, _ = auth_headers(username="isoA3")
    headers_b, _ = auth_headers(username="isoB3")
    _create_bill(client, headers_a)

    dash_b = client.get("/api/dashboard", headers=headers_b).get_json()
    assert dash_b["caught_up"] is True
    assert dash_b["urgent"] == []
    assert dash_b["monthly_recurring_total"] == "0.00"

    month = date.today().strftime("%Y-%m")
    history_b = client.get(f"/api/history?month={month}", headers=headers_b).get_json()
    assert history_b["total"] == 0


def test_settings_isolation(client, auth_headers):
    headers_a, _ = auth_headers(username="isoA4")
    headers_b, _ = auth_headers(username="isoB4")

    client.patch("/api/settings", headers=headers_a, json={"reminder_7_days": True})
    settings_b = client.get("/api/settings", headers=headers_b).get_json()["settings"]
    assert settings_b["reminder_7_days"] is False  # default, unaffected by A's change


def test_feedback_isolation(client, auth_headers):
    headers_a, _ = auth_headers(username="isoA5")
    headers_b, _ = auth_headers(username="isoB5")

    resp = client.post("/api/feedback", headers=headers_a, json={"type": "bug", "message": "Something broke"})
    feedback_id = resp.get_json()["feedback"]["id"]

    assert client.get(f"/api/feedback/{feedback_id}", headers=headers_b).status_code == 403

    b_list = client.get("/api/feedback", headers=headers_b).get_json()["feedback"]
    assert b_list == []


def test_non_admin_cannot_access_admin_endpoints(client, auth_headers):
    headers, _ = auth_headers(username="isoNonAdmin")
    assert client.get("/api/admin/feedback").status_code == 401
    assert client.get("/api/admin/feedback", headers=headers).status_code == 403

    resp = client.post("/api/feedback", headers=headers, json={"type": "bug", "message": "x"})
    feedback_id = resp.get_json()["feedback"]["id"]
    assert client.patch(f"/api/admin/feedback/{feedback_id}", headers=headers, json={"status": "resolved"}).status_code == 403


def test_client_supplied_user_id_is_ignored(client, auth_headers):
    """The API must derive identity solely from the JWT -- a client cannot
    override it by passing a user_id in the query string or body."""
    headers_a, user_id_a = auth_headers(username="isoSpoofA")
    headers_b, user_id_b = auth_headers(username="isoSpoofB")
    _create_bill(client, headers_a)

    # Attempting to pass another user's id via query string must have no effect.
    resp = client.get(f"/api/bills?status=all&user_id={user_id_a}", headers=headers_b)
    assert resp.status_code == 200
    assert resp.get_json()["bills"] == []
