"""
The daily/hourly reminder scan. Designed to be safe to run as often as
desired (Render Cron Job, hourly recommended so each user's local day
boundary is caught promptly) -- the unique constraint on
(bill_occurrence_id, type, channel) in the notifications table makes every
send idempotent, so re-running the scan never double-sends and a missed
run is simply caught on the next one.
"""
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models import User, BillOccurrence, BillDefinition, Notification, NotificationType, NotificationChannel
from app.services.status import user_today
from app.services.email import send_bill_reminder_email, EmailUnavailableError
from app.services.push import send_push_to_user, PushUnavailableError

logger = logging.getLogger("billio.scheduler")

_TYPE_BY_DAYS_DIFF = {
    7: (NotificationType.REMINDER_7_DAY, "reminder_7_days"),
    3: (NotificationType.REMINDER_3_DAY, "reminder_3_days"),
    1: (NotificationType.REMINDER_1_DAY, "reminder_1_day"),
    0: (NotificationType.REMINDER_DUE_TODAY, "reminder_due_today"),
    -1: (NotificationType.REMINDER_OVERDUE_1, "overdue_reminders"),
    -2: (NotificationType.REMINDER_OVERDUE_2, "overdue_reminders"),
    -3: (NotificationType.REMINDER_OVERDUE_3, "overdue_reminders"),
}

_LABEL_BY_TYPE = {
    NotificationType.REMINDER_7_DAY: "is due in 7 days",
    NotificationType.REMINDER_3_DAY: "is due in 3 days",
    NotificationType.REMINDER_1_DAY: "is due tomorrow",
    NotificationType.REMINDER_DUE_TODAY: "is due today",
    NotificationType.REMINDER_OVERDUE_1: "is 1 day overdue",
    NotificationType.REMINDER_OVERDUE_2: "is 2 days overdue",
    NotificationType.REMINDER_OVERDUE_3: "is 3 days overdue",
}


def _already_sent(occurrence_id, notification_type, channel) -> bool:
    return (
        db.session.query(Notification.id)
        .filter_by(bill_occurrence_id=occurrence_id, type=notification_type, channel=channel)
        .first()
        is not None
    )


def _record_sent(user_id, occurrence_id, notification_type, channel):
    db.session.add(
        Notification(user_id=user_id, bill_occurrence_id=occurrence_id, type=notification_type, channel=channel)
    )


def run_reminder_scan() -> dict:
    stats = {"users_scanned": 0, "push_sent": 0, "email_sent": 0, "errors": 0}

    users = User.query.filter_by(is_active=True).all()
    for user in users:
        stats["users_scanned"] += 1
        today = user_today(user.timezone)
        settings = user.settings
        if settings is None:
            continue

        occurrences = (
            db.session.query(BillOccurrence, BillDefinition)
            .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
            .filter(BillOccurrence.user_id == user.id, BillOccurrence.is_paid.is_(False))
            .all()
        )

        for occurrence, bill in occurrences:
            days_diff = (occurrence.due_date - today).days
            mapping = _TYPE_BY_DAYS_DIFF.get(days_diff)
            if mapping is None:
                continue
            notification_type, setting_field = mapping
            if not getattr(settings, setting_field, False):
                continue

            label = _LABEL_BY_TYPE[notification_type]

            if settings.push_notifications and not _already_sent(occurrence.id, notification_type, NotificationChannel.PUSH):
                try:
                    delivered = send_push_to_user(
                        user,
                        {
                            "title": "Billio",
                            "body": (
                                "You have a bill reminder"
                                if settings.private_notification_text
                                else f"{bill.name} {label}"
                            ),
                            "url": f"/bills/{bill.id}?occurrence={occurrence.id}",
                            "amount": None if settings.private_notification_text else str(occurrence.amount),
                        },
                    )
                    if delivered:
                        _record_sent(user.id, occurrence.id, notification_type, NotificationChannel.PUSH)
                        stats["push_sent"] += 1
                except PushUnavailableError:
                    stats["errors"] += 1
                    logger.error("push_reminder_failed", extra={"extra_fields": {"user_id": str(user.id)}})

            if (
                settings.email_notifications
                and user.email
                and user.email_verified_at is not None
                and not _already_sent(occurrence.id, notification_type, NotificationChannel.EMAIL)
            ):
                try:
                    from flask import current_app

                    deep_link = f"{current_app.config['FRONTEND_BASE_URL']}/bills/{bill.id}?occurrence={occurrence.id}"
                    send_bill_reminder_email(
                        user.email,
                        user.first_name,
                        bill.name,
                        str(occurrence.amount),
                        label,
                        deep_link,
                        settings.private_notification_text,
                    )
                    _record_sent(user.id, occurrence.id, notification_type, NotificationChannel.EMAIL)
                    stats["email_sent"] += 1
                except EmailUnavailableError:
                    stats["errors"] += 1
                    logger.error("email_reminder_failed", extra={"extra_fields": {"user_id": str(user.id)}})

        db.session.commit()

    logger.info("reminder_scan_complete", extra={"extra_fields": stats})
    return stats
