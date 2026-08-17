from datetime import date, timedelta


def _create_bill(client, headers, **overrides):
    payload = {
        "name": "Netflix",
        "amount": "17.99",
        "recurrence": "monthly",
        "due_date": (date.today() + timedelta(days=5)).isoformat(),
        "category": "entertainment",
    }
    payload.update(overrides)
    resp = client.post("/api/bills", headers=headers, json=payload)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["bill"]


def test_create_bill_rejects_negative_amount(client, auth_headers):
    headers, _ = auth_headers(username="billneg")
    resp = client.post(
        "/api/bills",
        headers=headers,
        json={"name": "Bad", "amount": "-5.00", "recurrence": "monthly", "due_date": date.today().isoformat()},
    )
    assert resp.status_code == 422


def test_create_bill_rejects_invalid_recurrence(client, auth_headers):
    headers, _ = auth_headers(username="billrec")
    resp = client.post(
        "/api/bills",
        headers=headers,
        json={"name": "Bad", "amount": "5.00", "recurrence": "daily", "due_date": date.today().isoformat()},
    )
    assert resp.status_code == 422


def test_create_bill_generates_first_occurrence(client, auth_headers):
    headers, _ = auth_headers(username="billocc")
    bill = _create_bill(client, headers)
    occs = client.get("/api/occurrences", headers=headers).get_json()["occurrences"]
    assert len(occs) == 1
    assert occs[0]["bill_definition_id"] == bill["id"]


def test_mark_paid_generates_next_occurrence_for_recurring_bill(client, auth_headers):
    headers, _ = auth_headers(username="billmarkpaid")
    _create_bill(client, headers, recurrence="monthly", due_date=date.today().isoformat())
    occ = client.get("/api/occurrences", headers=headers).get_json()["occurrences"][0]

    resp = client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["occurrence"]["is_paid"] is True
    assert "next_occurrence" in body
    assert body["next_occurrence"]["is_paid"] is False


def test_mark_paid_does_not_generate_next_for_one_off_bill(client, auth_headers):
    headers, _ = auth_headers(username="billoneoff")
    _create_bill(client, headers, recurrence="none", due_date=date.today().isoformat())
    occ = client.get("/api/occurrences", headers=headers).get_json()["occurrences"][0]

    resp = client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)
    assert resp.status_code == 200
    assert "next_occurrence" not in resp.get_json()


def test_mark_paid_twice_returns_conflict_not_double_processed(client, auth_headers):
    headers, _ = auth_headers(username="billdouble")
    _create_bill(client, headers, recurrence="monthly", due_date=date.today().isoformat())
    occ = client.get("/api/occurrences", headers=headers).get_json()["occurrences"][0]

    first = client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)
    assert first.status_code == 200
    second = client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)
    assert second.status_code == 409

    occs = client.get("/api/occurrences", headers=headers).get_json()["occurrences"]
    # Exactly 2 occurrences total (original + one generated next), not 3.
    assert len(occs) == 2


def test_editing_amount_does_not_rewrite_paid_history(client, auth_headers):
    headers, _ = auth_headers(username="billeditamt")
    bill = _create_bill(client, headers, recurrence="monthly", amount="17.99", due_date=date.today().isoformat())
    occ = client.get("/api/occurrences", headers=headers).get_json()["occurrences"][0]
    client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)

    client.patch(f"/api/bills/{bill['id']}", headers=headers, json={"amount": "22.99"})

    paid_history = client.get("/api/occurrences?status=paid", headers=headers).get_json()["occurrences"]
    assert paid_history[0]["amount"] == "17.99"  # historical record untouched

    upcoming = client.get("/api/occurrences?status=upcoming", headers=headers).get_json()["occurrences"]
    if upcoming:
        assert upcoming[0]["amount"] == "22.99"  # future occurrence picks up new amount


def test_cancel_bill_preserves_paid_history_but_removes_future_unpaid(client, auth_headers):
    headers, _ = auth_headers(username="billcancel")
    bill = _create_bill(client, headers, recurrence="monthly", due_date=date.today().isoformat())
    occ = client.get("/api/occurrences", headers=headers).get_json()["occurrences"][0]
    client.post(f"/api/occurrences/{occ['id']}/mark-paid", headers=headers)  # generates a future occurrence

    resp = client.delete(f"/api/bills/{bill['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["bill"]["status"] == "cancelled"

    paid = client.get("/api/occurrences?status=paid", headers=headers).get_json()["occurrences"]
    assert len(paid) == 1  # historical paid record survives cancellation

    all_occs = client.get("/api/occurrences", headers=headers).get_json()["occurrences"]
    assert len(all_occs) == 1  # the future not-yet-due occurrence was removed


def test_cancelled_bill_cannot_be_edited(client, auth_headers):
    headers, _ = auth_headers(username="billeditcancelled")
    bill = _create_bill(client, headers)
    client.delete(f"/api/bills/{bill['id']}", headers=headers)
    resp = client.patch(f"/api/bills/{bill['id']}", headers=headers, json={"name": "New Name"})
    assert resp.status_code == 422


def test_dashboard_monthly_recurring_total_computed_correctly(client, auth_headers):
    headers, _ = auth_headers(username="billmonthly")
    _create_bill(client, headers, name="Monthly1", amount="10.00", recurrence="monthly")
    _create_bill(client, headers, name="Yearly1", amount="120.00", recurrence="yearly")
    _create_bill(client, headers, name="OneOff", amount="500.00", recurrence="none")

    dashboard = client.get("/api/dashboard", headers=headers).get_json()
    # 10.00 (monthly) + 120/12=10.00 (yearly) = 20.00; the one-off is excluded.
    assert dashboard["monthly_recurring_total"] == "20.00"
