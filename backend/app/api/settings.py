from flask import Blueprint, jsonify

from app.extensions import db
from app.schemas import serialize_settings
from app.utils.security import get_current_user
from app.utils.validation import get_json_body

bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_BOOL_FIELDS = {
    "push_notifications",
    "email_notifications",
    "reminder_7_days",
    "reminder_3_days",
    "reminder_1_day",
    "reminder_due_today",
    "overdue_reminders",
    "private_notification_text",
}


@bp.get("")
def get_settings():
    user = get_current_user()
    return jsonify({"settings": serialize_settings(user.settings)}), 200


@bp.patch("")
def update_settings():
    user = get_current_user()
    body = get_json_body()
    settings = user.settings

    for field in _BOOL_FIELDS:
        if field in body:
            value = body[field]
            if not isinstance(value, bool):
                from app.errors import ValidationError

                raise ValidationError(f"{field} must be true or false.", details={"field": field})
            setattr(settings, field, value)

    db.session.commit()
    return jsonify({"settings": serialize_settings(settings)}), 200
