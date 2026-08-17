"""
Dashboard aggregation queries. Per spec, totals are computed in SQL (not by
summing in JavaScript/Python) so the numbers are always consistent with
what the database actually holds, and so this scales past what would be
comfortable to page into application memory.
"""
from decimal import Decimal

from sqlalchemy import case, func

from app.extensions import db
from app.models import BillOccurrence, BillDefinition, BillStatus, RecurrenceType
from app.services.status import user_today

# Multiplier to normalize each recurrence cadence to a monthly-equivalent
# figure. Computed in SQL via a CASE expression against NUMERIC amounts, so
# Postgres does the arithmetic with exact decimal division.
_MONTHLY_FACTOR = {
    RecurrenceType.WEEKLY: Decimal("52") / Decimal("12"),
    RecurrenceType.MONTHLY: Decimal("1"),
    RecurrenceType.QUARTERLY: Decimal("1") / Decimal("3"),
    RecurrenceType.YEARLY: Decimal("1") / Decimal("12"),
}


def monthly_recurring_total(user) -> Decimal:
    factor_case = case(
        (BillDefinition.recurrence == RecurrenceType.WEEKLY, _MONTHLY_FACTOR[RecurrenceType.WEEKLY]),
        (BillDefinition.recurrence == RecurrenceType.MONTHLY, _MONTHLY_FACTOR[RecurrenceType.MONTHLY]),
        (BillDefinition.recurrence == RecurrenceType.QUARTERLY, _MONTHLY_FACTOR[RecurrenceType.QUARTERLY]),
        (BillDefinition.recurrence == RecurrenceType.YEARLY, _MONTHLY_FACTOR[RecurrenceType.YEARLY]),
        else_=Decimal("0"),
    )
    total = (
        db.session.query(func.coalesce(func.sum(BillDefinition.default_amount * factor_case), Decimal("0")))
        .filter(
            BillDefinition.user_id == user.id,
            BillDefinition.status == BillStatus.ACTIVE,
            BillDefinition.recurrence != RecurrenceType.NONE,
        )
        .scalar()
    )
    return Decimal(total).quantize(Decimal("0.01"))


def get_dashboard(user) -> dict:
    today = user_today(user.timezone)

    urgent_rows = (
        db.session.query(BillOccurrence, BillDefinition)
        .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
        .filter(
            BillOccurrence.user_id == user.id,
            BillOccurrence.is_paid.is_(False),
            BillOccurrence.due_date <= today,
        )
        .order_by(BillOccurrence.due_date.asc())
        .all()
    )

    upcoming_rows = (
        db.session.query(BillOccurrence, BillDefinition)
        .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
        .filter(
            BillOccurrence.user_id == user.id,
            BillOccurrence.is_paid.is_(False),
            BillOccurrence.due_date > today,
        )
        .order_by(BillOccurrence.due_date.asc())
        .limit(25)
        .all()
    )

    recently_paid_rows = (
        db.session.query(BillOccurrence, BillDefinition)
        .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
        .filter(BillOccurrence.user_id == user.id, BillOccurrence.is_paid.is_(True))
        .order_by(BillOccurrence.paid_at.desc())
        .limit(10)
        .all()
    )

    outstanding_total = (
        db.session.query(func.coalesce(func.sum(BillOccurrence.amount), Decimal("0")))
        .filter(
            BillOccurrence.user_id == user.id,
            BillOccurrence.is_paid.is_(False),
            BillOccurrence.due_date <= today,
        )
        .scalar()
    )

    caught_up = len(urgent_rows) == 0

    return {
        "caught_up": caught_up,
        "attention_count": len(urgent_rows),
        "outstanding_total": Decimal(outstanding_total).quantize(Decimal("0.01")),
        "monthly_recurring_total": monthly_recurring_total(user),
        "urgent": urgent_rows,
        "upcoming": upcoming_rows,
        "recently_paid": recently_paid_rows,
        "next_upcoming": upcoming_rows[0] if upcoming_rows else None,
    }
