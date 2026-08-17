"""
Core bill/occurrence business logic. This module is the single place where
bills are created, edited, cancelled, and marked paid -- used by both the
REST API (app/api/bills.py, app/api/occurrences.py) and the AI assistant's
function-calling layer (app/services/assistant.py), so every code path
enforces the exact same ownership checks, validation, and recurrence rules.
Never bypass this module to touch BillDefinition/BillOccurrence directly
from a route.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.errors import NotFoundError, ConflictError, ValidationError
from app.models import BillDefinition, BillOccurrence, Payment, BillStatus, RecurrenceType
from app.services.recurrence import first_occurrence_due_date, next_due_date
from app.services.status import user_today


def get_owned_bill(user, bill_id) -> BillDefinition:
    bill = BillDefinition.query.filter_by(id=bill_id, user_id=user.id).first()
    if bill is None:
        raise NotFoundError("Bill not found.")
    return bill


def get_owned_occurrence(user, occurrence_id) -> BillOccurrence:
    occurrence = BillOccurrence.query.filter_by(id=occurrence_id, user_id=user.id).first()
    if occurrence is None:
        raise NotFoundError("Bill occurrence not found.")
    return occurrence


def list_bills(user, *, status: BillStatus | None = None):
    query = BillDefinition.query.filter_by(user_id=user.id)
    if status is not None:
        query = query.filter_by(status=status)
    else:
        query = query.filter_by(status=BillStatus.ACTIVE)
    return query.order_by(BillDefinition.name.asc()).all()


def create_bill(
    user,
    *,
    name: str,
    default_amount: Decimal,
    recurrence: RecurrenceType,
    first_due_date,
    category: str | None = None,
    notes: str | None = None,
) -> BillDefinition:
    bill = BillDefinition(
        user_id=user.id,
        name=name,
        default_amount=default_amount,
        recurrence=recurrence,
        category=category,
        notes=notes,
        first_due_date=first_due_date,
        status=BillStatus.ACTIVE,
    )
    db.session.add(bill)
    db.session.flush()

    occurrence = BillOccurrence(
        bill_definition_id=bill.id,
        user_id=user.id,
        amount=default_amount,
        due_date=first_occurrence_due_date(first_due_date),
        is_paid=False,
    )
    db.session.add(occurrence)
    db.session.commit()
    return bill


def update_bill(
    user,
    bill_id,
    *,
    name: str | None = None,
    default_amount: Decimal | None = None,
    category: str | None = None,
    notes: str | None = None,
    reschedule_due_date=None,
) -> BillDefinition:
    bill = get_owned_bill(user, bill_id)
    if bill.status != BillStatus.ACTIVE:
        raise ValidationError("Cancelled bills cannot be edited.")

    if name is not None:
        bill.name = name
    if category is not None:
        bill.category = category
    if notes is not None:
        bill.notes = notes

    today = user_today(user.timezone)

    if default_amount is not None and default_amount != bill.default_amount:
        bill.default_amount = default_amount
        # Historical fidelity: only NOT-YET-DUE, unpaid occurrences pick up
        # the new amount. Anything due today, overdue, or already paid keeps
        # its original snapshot amount so past records are never rewritten.
        future_occurrences = BillOccurrence.query.filter(
            BillOccurrence.bill_definition_id == bill.id,
            BillOccurrence.is_paid.is_(False),
            BillOccurrence.due_date > today,
        ).all()
        for occ in future_occurrences:
            occ.amount = default_amount

    if reschedule_due_date is not None:
        # Reschedules the single "next" pending occurrence (used by e.g.
        # "move my electric bill to the 28th"). The bill's anchor
        # (first_due_date) is also updated so future recurrence math uses
        # the new date going forward.
        pending = (
            BillOccurrence.query.filter(
                BillOccurrence.bill_definition_id == bill.id,
                BillOccurrence.is_paid.is_(False),
            )
            .order_by(BillOccurrence.due_date.asc())
            .first()
        )
        bill.first_due_date = reschedule_due_date
        if pending is not None:
            existing = BillOccurrence.query.filter(
                BillOccurrence.bill_definition_id == bill.id,
                BillOccurrence.due_date == reschedule_due_date,
                BillOccurrence.id != pending.id,
            ).first()
            if existing is not None:
                raise ConflictError("An occurrence already exists on that date.")
            pending.due_date = reschedule_due_date

    db.session.commit()
    return bill


def cancel_bill(user, bill_id) -> BillDefinition:
    """Soft-delete: the bill stops generating new occurrences, but every
    occurrence/payment that already represents a real historical obligation
    (due today, overdue, or paid) is preserved untouched. Only purely future
    not-yet-due unpaid occurrences are removed, since those never became
    real obligations."""
    bill = get_owned_bill(user, bill_id)
    if bill.status == BillStatus.CANCELLED:
        return bill

    today = user_today(user.timezone)
    BillOccurrence.query.filter(
        BillOccurrence.bill_definition_id == bill.id,
        BillOccurrence.is_paid.is_(False),
        BillOccurrence.due_date > today,
    ).delete(synchronize_session=False)

    bill.status = BillStatus.CANCELLED
    db.session.commit()
    return bill


def query_occurrences(
    user,
    *,
    status: str | None = None,
    category: str | None = None,
    date_from=None,
    date_to=None,
    bill_id=None,
):
    """
    Returns a (still-unexecuted) SQLAlchemy query of (BillOccurrence,
    BillDefinition) tuples scoped to `user`, honoring the given filters.
    Callers execute/paginate it. `status` here is the derived
    upcoming/due_today/overdue/paid state, computed against the user's
    local "today" -- never a stored column.
    """
    today = user_today(user.timezone)

    query = (
        db.session.query(BillOccurrence, BillDefinition)
        .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
        .filter(BillOccurrence.user_id == user.id)
    )

    if bill_id is not None:
        query = query.filter(BillOccurrence.bill_definition_id == bill_id)
    if category is not None:
        query = query.filter(BillDefinition.category == category)
    if date_from is not None:
        query = query.filter(BillOccurrence.due_date >= date_from)
    if date_to is not None:
        query = query.filter(BillOccurrence.due_date <= date_to)

    if status == "paid":
        query = query.filter(BillOccurrence.is_paid.is_(True)).order_by(BillOccurrence.paid_at.desc())
    elif status == "upcoming":
        query = query.filter(BillOccurrence.is_paid.is_(False), BillOccurrence.due_date > today).order_by(
            BillOccurrence.due_date.asc()
        )
    elif status == "due_today":
        query = query.filter(BillOccurrence.is_paid.is_(False), BillOccurrence.due_date == today).order_by(
            BillOccurrence.due_date.asc()
        )
    elif status == "overdue":
        query = query.filter(BillOccurrence.is_paid.is_(False), BillOccurrence.due_date < today).order_by(
            BillOccurrence.due_date.asc()
        )
    elif status == "unpaid":
        query = query.filter(BillOccurrence.is_paid.is_(False)).order_by(BillOccurrence.due_date.asc())
    else:
        query = query.order_by(BillOccurrence.due_date.asc())

    return query


def mark_occurrence_paid(user, occurrence_id) -> tuple[BillOccurrence, BillOccurrence | None, Payment]:
    """
    Marks an occurrence paid, writes an immutable Payment record, and -- if
    the bill recurs and is still active -- generates the next occurrence.
    Uses SELECT ... FOR UPDATE to serialize concurrent requests against the
    same occurrence (double-tap on "Mark as paid", or two browser tabs),
    and is idempotent: a second call on an already-paid occurrence returns a
    clear conflict rather than double-processing.
    """
    occurrence = (
        BillOccurrence.query.filter_by(id=occurrence_id, user_id=user.id).with_for_update().first()
    )
    if occurrence is None:
        raise NotFoundError("Bill occurrence not found.")
    if occurrence.is_paid:
        raise ConflictError("This bill has already been marked as paid.", error_code="already_paid")

    bill = BillDefinition.query.filter_by(id=occurrence.bill_definition_id).with_for_update().first()

    now = datetime.now(timezone.utc)
    occurrence.is_paid = True
    occurrence.paid_at = now

    payment = Payment(
        user_id=user.id,
        bill_occurrence_id=occurrence.id,
        bill_definition_id=bill.id if bill else None,
        amount_paid=occurrence.amount,
        due_date=occurrence.due_date,
        paid_at=now,
        bill_name=bill.name if bill else "Unknown bill",
        category=bill.category if bill else None,
    )
    db.session.add(payment)

    new_occurrence = None
    if bill is not None and bill.status == BillStatus.ACTIVE and bill.recurrence != RecurrenceType.NONE:
        next_date = next_due_date(bill.first_due_date, bill.recurrence, occurrence.due_date)
        if next_date is not None:
            existing = BillOccurrence.query.filter_by(
                bill_definition_id=bill.id, due_date=next_date
            ).first()
            if existing is None:
                new_occurrence = BillOccurrence(
                    bill_definition_id=bill.id,
                    user_id=user.id,
                    amount=bill.default_amount,
                    due_date=next_date,
                    is_paid=False,
                )
                db.session.add(new_occurrence)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # A concurrent request already generated the next occurrence or
        # processed this payment -- treat as already handled.
        raise ConflictError("This bill was already processed.", error_code="already_paid")

    return occurrence, new_occurrence, payment
