"""
Serialization of SQLAlchemy models to JSON-safe dicts. Centralizing this
avoids accidentally leaking sensitive fields (password_hash, admin_note,
token hashes) from an ad-hoc `model.__dict__` somewhere in a route.
"""
from app.services.status import compute_status, urgency_for, user_today


def serialize_user(user, *, settings=None) -> dict:
    data = {
        "id": str(user.id),
        "first_name": user.first_name,
        "username": user.username,
        "email": user.email,
        "timezone": user.timezone,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }
    if settings is not None:
        data["settings"] = serialize_settings(settings)
    return data


def serialize_settings(settings) -> dict:
    return {
        "push_notifications": settings.push_notifications,
        "email_notifications": settings.email_notifications,
        "reminder_7_days": settings.reminder_7_days,
        "reminder_3_days": settings.reminder_3_days,
        "reminder_1_day": settings.reminder_1_day,
        "reminder_due_today": settings.reminder_due_today,
        "overdue_reminders": settings.overdue_reminders,
        "private_notification_text": settings.private_notification_text,
    }


def serialize_bill_definition(bill) -> dict:
    return {
        "id": str(bill.id),
        "name": bill.name,
        "default_amount": str(bill.default_amount),
        "recurrence": bill.recurrence.value,
        "category": bill.category,
        "notes": bill.notes,
        "reference_number": bill.reference_number,
        "first_due_date": bill.first_due_date.isoformat(),
        # Convenience for the edit form: monthly/yearly bills are edited by
        # day-of-month / month+day (no year -- see
        # app/services/recurrence.py), so these save the frontend from
        # having to parse first_due_date itself. They're always just the
        # day/month components of first_due_date; not separately stored.
        "day_of_month": bill.first_due_date.day,
        "month": bill.first_due_date.month,
        "status": bill.status.value,
        "created_at": bill.created_at.isoformat(),
        "updated_at": bill.updated_at.isoformat(),
    }


def serialize_occurrence(occurrence, *, user_tz: str, bill_name: str | None = None, category: str | None = None) -> dict:
    today = user_today(user_tz)
    paid_at_local = None
    if occurrence.paid_at is not None:
        from app.services.status import safe_zone

        paid_at_local = occurrence.paid_at.astimezone(safe_zone(user_tz)).date()
    urgency = urgency_for(occurrence.due_date, occurrence.is_paid, paid_at_local, today)

    return {
        "id": str(occurrence.id),
        "bill_definition_id": str(occurrence.bill_definition_id),
        "name": bill_name,
        "category": category,
        "amount": str(occurrence.amount),
        "due_date": occurrence.due_date.isoformat(),
        "is_paid": occurrence.is_paid,
        "paid_at": occurrence.paid_at.isoformat() if occurrence.paid_at else None,
        "status": urgency.status,
        "status_label": urgency.label,
        "urgency_level": urgency.urgency_level,
        "days": urgency.days,
    }


def serialize_payment(payment) -> dict:
    return {
        "id": str(payment.id),
        "bill_occurrence_id": str(payment.bill_occurrence_id),
        "bill_definition_id": str(payment.bill_definition_id) if payment.bill_definition_id else None,
        "bill_name": payment.bill_name,
        "category": payment.category,
        "amount_paid": str(payment.amount_paid),
        "due_date": payment.due_date.isoformat(),
        "paid_at": payment.paid_at.isoformat(),
    }


def serialize_feedback(feedback, *, is_admin: bool = False) -> dict:
    data = {
        "id": str(feedback.id),
        "type": feedback.type.value,
        "message": feedback.message,
        "rating": feedback.rating,
        "status": feedback.status.value,
        "created_at": feedback.created_at.isoformat(),
        "updated_at": feedback.updated_at.isoformat(),
    }
    if is_admin:
        data["user_id"] = f"user_{str(feedback.user_id)[:8]}"
        data["admin_note"] = feedback.admin_note
    return data


def serialize_document(document) -> dict:
    return {
        "id": str(document.id),
        "file_type": document.file_type,
        "file_size_bytes": document.file_size_bytes,
        "original_filename": document.original_filename,
        "bill_definition_id": str(document.bill_definition_id) if document.bill_definition_id else None,
        "bill_occurrence_id": str(document.bill_occurrence_id) if document.bill_occurrence_id else None,
        "created_at": document.created_at.isoformat(),
    }
