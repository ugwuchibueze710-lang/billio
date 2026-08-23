"""
Server-side request validation helpers. The frontend also validates for UX,
but every one of these checks is re-enforced here because client-side
validation can always be bypassed.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from email_validator import validate_email as _validate_email, EmailNotValidError
from flask import request

from app.errors import ValidationError
from app.models.enums import RecurrenceType, FeedbackType

MAX_AMOUNT = Decimal("1000000.00")
MIN_AMOUNT = Decimal("0.01")


def get_json_body() -> dict:
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        raise ValidationError("Request body must be valid JSON.")
    return body


def require_fields(body: dict, *fields: str) -> None:
    missing = [f for f in fields if body.get(f) in (None, "")]
    if missing:
        raise ValidationError(
            f"Missing required field(s): {', '.join(missing)}", details={"missing_fields": missing}
        )


def validate_string(value, field_name: str, *, min_len=1, max_len=500, required=True) -> str | None:
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required.", details={"field": field_name})
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.", details={"field": field_name})
    stripped = value.strip()
    if len(stripped) < min_len:
        raise ValidationError(f"{field_name} is too short.", details={"field": field_name})
    if len(stripped) > max_len:
        raise ValidationError(f"{field_name} is too long (max {max_len} characters).", details={"field": field_name})
    return stripped


def validate_email_optional(value) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError("Email must be a string.", details={"field": "email"})
    try:
        result = _validate_email(value, check_deliverability=False)
        return result.normalized
    except EmailNotValidError as exc:
        raise ValidationError(f"Invalid email address: {exc}", details={"field": "email"})


def validate_amount(value, field_name: str = "amount") -> Decimal:
    if value is None:
        raise ValidationError(f"{field_name} is required.", details={"field": field_name})
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid number.", details={"field": field_name})
    if amount.is_nan() or amount.is_infinite():
        raise ValidationError(f"{field_name} must be a valid number.", details={"field": field_name})
    if amount < MIN_AMOUNT:
        raise ValidationError(f"{field_name} must be greater than zero.", details={"field": field_name})
    if amount > MAX_AMOUNT:
        raise ValidationError(f"{field_name} is unreasonably large.", details={"field": field_name})
    # Reject more than 2 decimal places rather than silently rounding money.
    if amount.as_tuple().exponent < -2:
        raise ValidationError(f"{field_name} cannot have more than 2 decimal places.", details={"field": field_name})
    return amount.quantize(Decimal("0.01"))


def validate_date_field(value, field_name: str = "date") -> date:
    if value is None:
        raise ValidationError(f"{field_name} is required.", details={"field": field_name})
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a date string (YYYY-MM-DD).", details={"field": field_name})
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format.", details={"field": field_name})
    if parsed.year < 1970 or parsed.year > 2100:
        raise ValidationError(f"{field_name} is out of a reasonable range.", details={"field": field_name})
    return parsed


def validate_recurrence(value) -> RecurrenceType:
    if value is None:
        raise ValidationError("recurrence is required.", details={"field": "recurrence"})
    try:
        return RecurrenceType(value)
    except ValueError:
        raise ValidationError(
            f"recurrence must be one of: {', '.join(r.value for r in RecurrenceType)}",
            details={"field": "recurrence"},
        )


def validate_feedback_type(value) -> FeedbackType:
    if value is None:
        raise ValidationError("type is required.", details={"field": "type"})
    try:
        return FeedbackType(value)
    except ValueError:
        raise ValidationError(
            f"type must be one of: {', '.join(t.value for t in FeedbackType)}", details={"field": "type"}
        )


def validate_rating(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        rating = int(value)
    except (ValueError, TypeError):
        raise ValidationError("rating must be an integer between 1 and 5.", details={"field": "rating"})
    if rating < 1 or rating > 5:
        raise ValidationError("rating must be between 1 and 5.", details={"field": "rating"})
    return rating


def validate_timezone(value) -> str:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if not isinstance(value, str) or not value:
        raise ValidationError("timezone is required.", details={"field": "timezone"})
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Unrecognized timezone.", details={"field": "timezone"})
    return value


def validate_pagination(args) -> tuple[int, int]:
    try:
        page = max(int(args.get("page", 1)), 1)
    except (ValueError, TypeError):
        raise ValidationError("page must be a positive integer.")
    try:
        per_page = int(args.get("per_page", 20))
    except (ValueError, TypeError):
        raise ValidationError("per_page must be a positive integer.")
    per_page = max(1, min(per_page, 100))
    return page, per_page
