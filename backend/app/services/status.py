"""
Occurrence status is always computed at read time from (due_date, is_paid)
plus the user's local "today" -- it is never stored, so it can never drift
out of sync with the calendar. This module is the single source of truth
for that derivation, used by both the dashboard/history API and the
notification scheduler so their notion of "overdue" always agrees.
"""
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STATUS_UPCOMING = "upcoming"
STATUS_DUE_TODAY = "due_today"
STATUS_OVERDUE = "overdue"
STATUS_PAID = "paid"

# After this many days overdue, the app stops sending aggressive reminders
# (per product spec section 10) -- the bill still shows as overdue/unpaid
# indefinitely, it just stops generating new notification rows.
OVERDUE_NOTIFICATION_WINDOW_DAYS = 3


def safe_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def user_today(tz_name: str | None, *, now: datetime | None = None) -> date:
    tz = safe_zone(tz_name)
    moment = now.astimezone(tz) if now else datetime.now(tz)
    return moment.date()


def compute_status(due_date: date, is_paid: bool, today: date) -> str:
    if is_paid:
        return STATUS_PAID
    if due_date > today:
        return STATUS_UPCOMING
    if due_date == today:
        return STATUS_DUE_TODAY
    return STATUS_OVERDUE


@dataclass(frozen=True)
class UrgencyLabel:
    status: str
    label: str
    days: int  # positive = days away, 0 = due today, negative = days overdue
    urgency_level: int  # 0 normal, 1 approaching, 2 tomorrow, 3 due today, 4 overdue


def urgency_for(due_date: date, is_paid: bool, paid_at_local: date | None, today: date) -> UrgencyLabel:
    status = compute_status(due_date, is_paid, today)

    if status == STATUS_PAID:
        paid_label = f"Paid {paid_at_local.strftime('%b %-d')}" if paid_at_local else "Paid"
        return UrgencyLabel(status=status, label=paid_label, days=0, urgency_level=0)

    if status == STATUS_OVERDUE:
        days_over = (today - due_date).days
        label = f"{days_over} day{'s' if days_over != 1 else ''} overdue"
        return UrgencyLabel(status=status, label=label, days=-days_over, urgency_level=4)

    if status == STATUS_DUE_TODAY:
        return UrgencyLabel(status=status, label="Due today", days=0, urgency_level=3)

    days_away = (due_date - today).days
    if days_away == 1:
        return UrgencyLabel(status=status, label="Due tomorrow", days=1, urgency_level=2)
    if days_away <= 3:
        return UrgencyLabel(status=status, label=f"Due in {days_away} days", days=days_away, urgency_level=1)
    return UrgencyLabel(status=status, label=f"Due in {days_away} days", days=days_away, urgency_level=0)


def should_send_overdue_reminder(days_overdue: int) -> bool:
    return 1 <= days_overdue <= OVERDUE_NOTIFICATION_WINDOW_DAYS
