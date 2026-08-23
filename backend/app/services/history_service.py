from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func, case

from app.extensions import db
from app.errors import ValidationError
from app.models import BillOccurrence, BillDefinition


def parse_month(month_str: str) -> tuple[date, date]:
    """'YYYY-MM' -> (first_day, last_day) of that month."""
    try:
        year_str, month_num_str = month_str.split("-")
        year, month_num = int(year_str), int(month_num_str)
        if not (1 <= month_num <= 12) or not (1970 <= year <= 2100):
            raise ValueError
    except (ValueError, AttributeError):
        raise ValidationError("month must be in YYYY-MM format.")
    first_day = date(year, month_num, 1)
    last_day = date(year, month_num, monthrange(year, month_num)[1])
    return first_day, last_day


def list_available_months(user) -> list[str]:
    rows = (
        db.session.query(func.date_trunc("month", BillOccurrence.due_date))
        .filter(BillOccurrence.user_id == user.id)
        .distinct()
        .order_by(func.date_trunc("month", BillOccurrence.due_date).desc())
        .all()
    )
    return [row[0].strftime("%Y-%m") for row in rows]


def month_summary(user, month_str: str) -> dict:
    first_day, last_day = parse_month(month_str)

    row = (
        db.session.query(
            func.coalesce(func.sum(BillOccurrence.amount), Decimal("0")).label("expected"),
            func.coalesce(
                func.sum(case((BillOccurrence.is_paid.is_(True), BillOccurrence.amount), else_=0)), Decimal("0")
            ).label("paid"),
            func.coalesce(
                func.sum(case((BillOccurrence.is_paid.is_(False), BillOccurrence.amount), else_=0)), Decimal("0")
            ).label("outstanding"),
            func.count(BillOccurrence.id).label("bill_count"),
            func.coalesce(func.sum(case((BillOccurrence.is_paid.is_(True), 1), else_=0)), 0).label("paid_count"),
        )
        .filter(
            BillOccurrence.user_id == user.id,
            BillOccurrence.due_date >= first_day,
            BillOccurrence.due_date <= last_day,
        )
        .one()
    )

    return {
        "month": month_str,
        "expected_total": Decimal(row.expected).quantize(Decimal("0.01")),
        "paid_total": Decimal(row.paid).quantize(Decimal("0.01")),
        "outstanding_total": Decimal(row.outstanding).quantize(Decimal("0.01")),
        "bill_count": row.bill_count,
        "paid_count": row.paid_count,
    }
