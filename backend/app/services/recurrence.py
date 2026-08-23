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
from calendar import monthrange
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.models.enums import RecurrenceType


def _months_between(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def resolve_monthly_due_date(today: date, day_of_month: int) -> date:
    """
    Given just a day-of-month (1-31, deliberately no year -- the user should
    never have to think about what year a recurring monthly bill is "in")
    and 'today', returns the concrete next occurrence of that day: this
    month if it hasn't passed yet (today counts as not-yet-passed), otherwise
    next month. A day that doesn't exist in the target month (e.g. 31 in a
    30-day month) is clamped to that month's real last day -- the same
    clamping behavior next_due_date() above already applies to every later
    cycle of a monthly bill, so the very first occurrence behaves
    identically to every one after it.

    This is the same logic the "Describe it" natural-language flow has used
    for its due_day -> due_date resolution (see app/api/ai.py); manual entry
    and PDF/photo extraction now both route through this one function too,
    rather than three separate copies of the same date math.

    Raises ValueError if day_of_month is out of [1, 31].
    """
    if not (1 <= day_of_month <= 31):
        raise ValueError("Day of month must be between 1 and 31.")

    year, month = today.year, today.month
    clamped_day = min(day_of_month, monthrange(year, month)[1])
    candidate = date(year, month, clamped_day)
    if candidate < today:
        month += 1
        if month > 12:
            month = 1
            year += 1
        clamped_day = min(day_of_month, monthrange(year, month)[1])
        candidate = date(year, month, clamped_day)
    return candidate


def resolve_annual_due_date(today: date, month: int, day: int) -> date:
    """
    Given just a month + day-of-month (1-12, 1-31, deliberately no year)
    and 'today', returns the concrete next occurrence: this year if it
    hasn't passed yet (today counts as not-yet-passed), otherwise next
    year. Feb 29 clamps to Feb 28 in a target year that isn't a leap year,
    same clamping principle as resolve_monthly_due_date above.

    Raises ValueError if month/day are out of range.
    """
    if not (1 <= month <= 12):
        raise ValueError("Month must be between 1 and 12.")
    if not (1 <= day <= 31):
        raise ValueError("Day must be between 1 and 31.")

    year = today.year
    clamped_day = min(day, monthrange(year, month)[1])
    candidate = date(year, month, clamped_day)
    if candidate < today:
        year += 1
        clamped_day = min(day, monthrange(year, month)[1])
        candidate = date(year, month, clamped_day)
    return candidate


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
