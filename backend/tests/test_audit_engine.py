from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import User, Payment, BillDefinition, BillOccurrence, RecurrenceType, BillStatus
from app.services import audit_engine


def _make_payment(user_id, bill_name, amount, paid_date, category="utilities"):
    """Creates a real BillDefinition + BillOccurrence to satisfy the
    payments table's foreign keys, then returns the (uncommitted) Payment
    row referencing them."""
    bill = BillDefinition(
        user_id=user_id,
        name=bill_name,
        default_amount=Decimal(amount),
        recurrence=RecurrenceType.NONE,
        category=category,
        first_due_date=paid_date,
        status=BillStatus.ACTIVE,
    )
    db.session.add(bill)
    db.session.flush()

    occurrence = BillOccurrence(
        bill_definition_id=bill.id,
        user_id=user_id,
        amount=Decimal(amount),
        due_date=paid_date,
        is_paid=True,
        paid_at=datetime(paid_date.year, paid_date.month, paid_date.day, 12, 0, tzinfo=timezone.utc),
    )
    db.session.add(occurrence)
    db.session.flush()

    return Payment(
        user_id=user_id,
        bill_occurrence_id=occurrence.id,
        bill_definition_id=bill.id,
        amount_paid=Decimal(amount),
        due_date=paid_date,
        paid_at=datetime(paid_date.year, paid_date.month, paid_date.day, 12, 0, tzinfo=timezone.utc),
        bill_name=bill_name,
        category=category,
    )


@pytest.fixture
def user_id(app, make_user):
    uid, _ = make_user(username="audituser")
    return uid


def test_period_totals_decimal_precision(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "Electric", "143.27", date(2026, 8, 5)))
        db.session.add(_make_payment(user_id, "Water", "0.10", date(2026, 8, 6)))
        db.session.commit()

        user = User.query.get(user_id)
        totals = audit_engine.period_totals(user, date(2026, 8, 1), date(2026, 8, 31))
        assert totals["total"] == Decimal("143.37")
        assert totals["payment_count"] == 2


def test_period_totals_no_bills_returns_zero(app, user_id):
    with app.app_context():
        user = User.query.get(user_id)
        totals = audit_engine.period_totals(user, date(2026, 8, 1), date(2026, 8, 31))
        assert totals["total"] == Decimal("0.00")
        assert totals["payment_count"] == 0


def test_compare_identifies_largest_driver(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "Electric", "300.00", date(2026, 7, 5)))
        db.session.add(_make_payment(user_id, "Electric", "480.00", date(2026, 8, 5)))
        db.session.add(_make_payment(user_id, "Insurance", "150.00", date(2026, 7, 6)))
        db.session.add(_make_payment(user_id, "Insurance", "150.00", date(2026, 8, 6)))
        db.session.commit()

        user = User.query.get(user_id)
        current = audit_engine.period_totals(user, date(2026, 8, 1), date(2026, 8, 31))
        previous = audit_engine.period_totals(user, date(2026, 7, 1), date(2026, 7, 31))
        comparison = audit_engine.compare(current, previous)

        assert comparison["difference"] == Decimal("180.00")
        assert comparison["largest_increases"][0]["name"] == "Electric"
        assert comparison["largest_increases"][0]["difference"] == Decimal("180.00")


def test_compare_detects_newly_appearing_and_disappeared_bills(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "OldGym", "40.00", date(2026, 7, 10)))
        db.session.add(_make_payment(user_id, "NewStreaming", "12.00", date(2026, 8, 10)))
        db.session.commit()

        user = User.query.get(user_id)
        current = audit_engine.period_totals(user, date(2026, 8, 1), date(2026, 8, 31))
        previous = audit_engine.period_totals(user, date(2026, 7, 1), date(2026, 7, 31))
        comparison = audit_engine.compare(current, previous)

        assert "NewStreaming" in comparison["newly_appearing_bills"]
        assert "OldGym" in comparison["disappeared_bills"]


def test_multiple_payments_close_together_detected(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "Netflix", "17.99", date(2026, 8, 1)))
        db.session.add(_make_payment(user_id, "Netflix", "17.99", date(2026, 8, 3)))
        db.session.commit()

        user = User.query.get(user_id)
        current = audit_engine.period_totals(user, date(2026, 8, 1), date(2026, 8, 31))
        flagged = audit_engine.multiple_payments_close_together(current["bill_payment_dates"])
        assert any(f["bill_name"] == "Netflix" for f in flagged)


def test_insufficient_history_detected(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "Netflix", "17.99", date.today()))
        db.session.commit()

        user = User.query.get(user_id)
        days = audit_engine.data_sufficiency_days(user)
        # Only one occurrence with today's due date -> ~0 days of history
        assert days == 0


def test_validate_narrative_numbers_rejects_hallucinated_figure():
    known = {"143.27", "300.00"}
    assert audit_engine.validate_narrative_numbers("You spent $143.27 this month.", known) is True
    assert audit_engine.validate_narrative_numbers("You spent $999999.99 this month.", known) is False


def test_deterministic_summary_never_uses_ai(app, user_id):
    with app.app_context():
        db.session.add(_make_payment(user_id, "Electric", "143.27", date(2026, 8, 5)))
        db.session.commit()
        user = User.query.get(user_id)
        dataset = audit_engine.run_audit(
            user, start=date(2026, 8, 1), end=date(2026, 8, 31), comparison_start=None, comparison_end=None, hard_audit=False
        )
        sentence = audit_engine.deterministic_summary_sentence(dataset)
        assert "143.27" in sentence


def test_audit_api_falls_back_to_deterministic_when_groq_unconfigured(client, auth_headers):
    """GROQ_API_KEY is unset in the test environment, so the audit endpoint
    must still return a usable, non-AI result rather than failing."""
    headers, _ = auth_headers(username="audit_api_user")
    resp = client.post(
        "/api/ai/audit",
        headers=headers,
        json={"question": "Why did I spend more this month?", "period": "this_month", "comparison": "previous_month"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ai_available"] is False
    assert body["explanation"]["source"] == "deterministic"
    assert "data" in body


def test_audit_isolation_between_users(app, client, auth_headers, make_user):
    headers_a, user_id_a = auth_headers(username="auditisoA")
    headers_b, user_id_b = auth_headers(username="auditisoB")

    with app.app_context():
        db.session.add(_make_payment(user_id_a, "SecretBill", "999.00", date.today()))
        db.session.commit()

    resp = client.post(
        "/api/ai/audit",
        headers=headers_b,
        json={"question": "audit everything", "period": "this_month", "comparison": "none"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["current_period"]["total"] == "0.00"
    assert "SecretBill" not in str(data)
