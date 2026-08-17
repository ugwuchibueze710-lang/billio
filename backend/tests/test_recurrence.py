"""
Pure unit tests for the recurrence engine (no DB needed) -- covers the
month-length, leap-year, and end-of-month edge cases called out explicitly
in the product spec.
"""
from datetime import date

from app.models.enums import RecurrenceType
from app.services.recurrence import next_due_date, occurrence_due_date_at_index


def test_monthly_31st_clamps_and_recovers_without_drift():
    anchor = date(2026, 1, 31)
    d1 = next_due_date(anchor, RecurrenceType.MONTHLY, anchor)
    assert d1 == date(2026, 2, 28)  # Feb 2026 has 28 days, 2026 not a leap year

    d2 = next_due_date(anchor, RecurrenceType.MONTHLY, d1)
    assert d2 == date(2026, 3, 31)  # back to 31st, NOT Feb 28 + 1 month = Mar 28

    d3 = next_due_date(anchor, RecurrenceType.MONTHLY, d2)
    assert d3 == date(2026, 4, 30)  # April only has 30 days

    d4 = next_due_date(anchor, RecurrenceType.MONTHLY, d3)
    assert d4 == date(2026, 5, 31)  # back to 31st again


def test_monthly_31st_leap_year_february():
    anchor = date(2024, 1, 31)  # 2024 is a leap year
    d1 = next_due_date(anchor, RecurrenceType.MONTHLY, anchor)
    assert d1 == date(2024, 2, 29)


def test_monthly_30th_through_february_non_leap():
    anchor = date(2027, 1, 30)
    d1 = next_due_date(anchor, RecurrenceType.MONTHLY, anchor)
    assert d1 == date(2027, 2, 28)
    d2 = next_due_date(anchor, RecurrenceType.MONTHLY, d1)
    assert d2 == date(2027, 3, 30)  # recovers to 30th, not Feb 28 + 1 month


def test_yearly_leap_day_anchor_non_leap_year_clamps():
    anchor = date(2024, 2, 29)
    d1 = next_due_date(anchor, RecurrenceType.YEARLY, anchor)
    assert d1 == date(2025, 2, 28)
    d2 = next_due_date(anchor, RecurrenceType.YEARLY, d1)
    assert d2 == date(2026, 2, 28)
    # 2028 is a leap year again -- should recover to the 29th
    d_leap = next_due_date(anchor, RecurrenceType.YEARLY, date(2027, 2, 28))
    assert d_leap == date(2028, 2, 29)


def test_quarterly_from_end_of_month_anchor():
    anchor = date(2026, 1, 31)
    d1 = next_due_date(anchor, RecurrenceType.QUARTERLY, anchor)
    assert d1 == date(2026, 4, 30)  # April has 30 days
    d2 = next_due_date(anchor, RecurrenceType.QUARTERLY, d1)
    assert d2 == date(2026, 7, 31)  # recovers to 31st


def test_weekly_simple_increment():
    anchor = date(2026, 3, 1)
    d1 = next_due_date(anchor, RecurrenceType.WEEKLY, anchor)
    assert d1 == date(2026, 3, 8)


def test_none_recurrence_has_no_next_date():
    anchor = date(2026, 3, 1)
    assert next_due_date(anchor, RecurrenceType.NONE, anchor) is None


def test_occurrence_due_date_at_index_matches_sequential_generation():
    anchor = date(2026, 1, 31)
    assert occurrence_due_date_at_index(anchor, RecurrenceType.MONTHLY, 0) == anchor
    assert occurrence_due_date_at_index(anchor, RecurrenceType.MONTHLY, 1) == date(2026, 2, 28)
    assert occurrence_due_date_at_index(anchor, RecurrenceType.MONTHLY, 2) == date(2026, 3, 31)


def test_dst_transition_dates_unaffected_since_dates_are_naive():
    # DST only affects datetimes with time-of-day, not pure calendar dates.
    # A bill due "on the 10th" of a DST-transition month should still land
    # on the 10th regardless of the clock shift.
    anchor = date(2026, 3, 10)
    d1 = next_due_date(anchor, RecurrenceType.MONTHLY, anchor)
    assert d1 == date(2026, 4, 10)
    assert d1.day == 10
