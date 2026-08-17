"""
Recurrence engine.

Computes due dates for recurring bills WITHOUT date drift. The key trick:
every occurrence's due date is always computed as an offset from the bill's
original `first_due_date` anchor (never incrementally from the previous,
possibly clamped, occurrence). This is what correctly handles:

  - Bills due on the 31st: Jan 31 -> Feb 28/29 (clamped) -> Mar 31 (back to
    31, NOT Feb 28 + 1 month = Mar 28). Using dateutil's relativedelta
    against the anchor date every time keeps the "intended" day-of-month
    correct even after a clamped month.
  - Leap years: Feb 29 anchor + 1 year -> Feb 28 in a non-leap year,
    automatically, via relativedelta's calendar-aware day clamping.
  - Quarterly/yearly bills spanning irregular month lengths.

dateutil.relativedelta.relativedelta(some_date, months=N) clamps the day
component to the target month's actual last day when the anchor day doesn't
exist in that month (e.g. day=31 in a 30-day month) -- this is exactly the
behavior required here, and it is well-tested library behavior rather than
hand-rolled date math.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.models.enums import RecurrenceType


def _months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def first_occurrence_due_date(first_due_date: date) -> date:
    """The bill's very first occurrence is simply its anchor date."""
    return first_due_date


def next_due_date(first_due_date: date, recurrence: RecurrenceType, current_due_date: date) -> date | None:
    """
    Given the due date of the occurrence that was just paid/completed,
    return the due date of the NEXT occurrence, or None if the bill does
    not recur.
    """
    if recurrence == RecurrenceType.NONE:
        return None

    if recurrence == RecurrenceType.WEEKLY:
        return current_due_date + timedelta(days=7)

    if recurrence == RecurrenceType.MONTHLY:
        n = _months_between(first_due_date, current_due_date) + 1
        return first_due_date + relativedelta(months=n)

    if recurrence == RecurrenceType.QUARTERLY:
        months_elapsed = _months_between(first_due_date, current_due_date)
        n_quarters = (months_elapsed // 3) + 1
        return first_due_date + relativedelta(months=3 * n_quarters)

    if recurrence == RecurrenceType.YEARLY:
        n = (current_due_date.year - first_due_date.year) + 1
        # Guard against being called with a current_due_date "before" the
        # anchor (shouldn't happen in practice, but keep n >= 1).
        n = max(n, 1)
        return first_due_date + relativedelta(years=n)

    raise ValueError(f"Unsupported recurrence type: {recurrence}")


def occurrence_due_date_at_index(first_due_date: date, recurrence: RecurrenceType, index: int) -> date:
    """
    Return the due date of the occurrence at `index` cycles after the
    anchor (index=0 is the anchor itself). Useful for backfilling or
    validating a sequence independent of any previously generated row.
    """
    if index == 0:
        return first_due_date
    if recurrence == RecurrenceType.NONE:
        raise ValueError("A non-recurring bill has only one occurrence (index 0).")
    if recurrence == RecurrenceType.WEEKLY:
        return first_due_date + timedelta(weeks=index)
    if recurrence == RecurrenceType.MONTHLY:
        return first_due_date + relativedelta(months=index)
    if recurrence == RecurrenceType.QUARTERLY:
        return first_due_date + relativedelta(months=3 * index)
    if recurrence == RecurrenceType.YEARLY:
        return first_due_date + relativedelta(years=index)
    raise ValueError(f"Unsupported recurrence type: {recurrence}")
