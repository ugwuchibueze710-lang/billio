import uuid as uuid_module

from flask import Blueprint, jsonify, request

from app.errors import ValidationError, NotFoundError
from app.extensions import db
from app.models import BillStatus, BillDocument, RecurrenceType
from app.schemas import serialize_bill_definition
from app.services import bill_service
from app.services.recurrence import resolve_monthly_due_date, resolve_annual_due_date
from app.services.status import user_today
from app.utils.security import get_current_user
from app.utils.validation import (
    get_json_body,
    require_fields,
    validate_string,
    validate_amount,
    validate_recurrence,
    validate_date_field,
)

bp = Blueprint("bills", __name__, url_prefix="/api/bills")


def _int_field(body, field_name):
    """Reads an integer field from the request body, raising a clear
    ValidationError (rather than a generic 400) if it's missing or not a
    whole number."""
    if field_name not in body or body.get(field_name) in (None, ""):
        raise ValidationError(f"{field_name} is required.", details={"field": field_name})
    try:
        return int(body.get(field_name))
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a whole number.", details={"field": field_name})


def _resolve_first_due_date(user, recurrence, body):
    """
    Monthly and yearly bills are entered as just a day-of-month (monthly)
    or a month + day-of-month (yearly) -- deliberately never a year, see
    app/services/recurrence.py -- and resolved here into a concrete anchor
    date using the user's local "today". Weekly, quarterly, and one-time
    bills are unchanged: they still require an explicit due_date.

    For backward compatibility (and so AI-assisted flows that already
    resolved a concrete due_date, like the "Describe it" tab and PDF/photo
    extraction, keep working unchanged), an explicit due_date is still
    accepted for monthly/yearly bills too if day_of_month/annual_month+day
    weren't sent.
    """
    if recurrence == RecurrenceType.MONTHLY and "day_of_month" in body:
        day_of_month = _int_field(body, "day_of_month")
        try:
            return resolve_monthly_due_date(user_today(user.timezone), day_of_month)
        except ValueError as exc:
            raise ValidationError(str(exc), details={"field": "day_of_month"})

    if recurrence == RecurrenceType.YEARLY and "annual_month" in body and "annual_day" in body:
        annual_month = _int_field(body, "annual_month")
        annual_day = _int_field(body, "annual_day")
        try:
            return resolve_annual_due_date(user_today(user.timezone), annual_month, annual_day)
        except ValueError as exc:
            raise ValidationError(str(exc), details={"field": "annual_month"})

    if "due_date" not in body:
        if recurrence == RecurrenceType.MONTHLY:
            raise ValidationError("day_of_month is required.", details={"field": "day_of_month"})
        if recurrence == RecurrenceType.YEARLY:
            raise ValidationError("annual_month and annual_day are required.", details={"field": "annual_month"})
        raise ValidationError("due_date is required.", details={"field": "due_date"})
    return validate_date_field(body.get("due_date"), "due_date")


@bp.get("")
def list_bills():
    user = get_current_user()
    status_param = request.args.get("status", "active")
    status = None
    if status_param == "active":
        status = BillStatus.ACTIVE
    elif status_param == "cancelled":
        status = BillStatus.CANCELLED
    elif status_param == "all":
        status = None
    else:
        raise ValidationError("status must be one of: active, cancelled, all.")

    bills = bill_service.list_bills(user, status=status) if status_param != "all" else bill_service.list_bills(user, status=None)
    if status_param == "all":
        from app.models import BillDefinition

        bills = BillDefinition.query.filter_by(user_id=user.id).order_by(BillDefinition.name.asc()).all()

    return jsonify({"bills": [serialize_bill_definition(b) for b in bills]}), 200


@bp.post("")
def create_bill():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "name", "amount", "recurrence")

    name = validate_string(body.get("name"), "name", min_len=1, max_len=200)
    amount = validate_amount(body.get("amount"))
    recurrence = validate_recurrence(body.get("recurrence"))
    due_date = _resolve_first_due_date(user, recurrence, body)
    category = validate_string(body.get("category"), "category", max_len=50, required=False)
    notes = validate_string(body.get("notes"), "notes", max_len=2000, required=False)
    reference_number = validate_string(
        body.get("reference_number"), "reference_number", max_len=100, required=False
    )

    bill = bill_service.create_bill(
        user,
        name=name,
        default_amount=amount,
        recurrence=recurrence,
        first_due_date=due_date,
        category=category,
        notes=notes,
        reference_number=reference_number,
    )

    document_id = body.get("document_id")
    if document_id:
        try:
            doc_uuid = uuid_module.UUID(str(document_id))
        except ValueError:
            raise ValidationError("document_id is not a valid identifier.")
        doc = BillDocument.query.filter_by(id=doc_uuid, user_id=user.id).first()
        if doc is None:
            raise NotFoundError("Uploaded document not found.")
        if doc.bill_definition_id is not None:
            raise ValidationError("This document is already attached to a bill.")
        doc.bill_definition_id = bill.id
        if bill.occurrences:
            doc.bill_occurrence_id = bill.occurrences[0].id
        db.session.commit()

    return jsonify({"bill": serialize_bill_definition(bill)}), 201


@bp.get("/<uuid:bill_id>")
def get_bill(bill_id):
    user = get_current_user()
    bill = bill_service.get_owned_bill(user, bill_id)
    return jsonify({"bill": serialize_bill_definition(bill)}), 200


@bp.patch("/<uuid:bill_id>")
def update_bill(bill_id):
    user = get_current_user()
    body = get_json_body()

    name = validate_string(body.get("name"), "name", max_len=200, required=False) if "name" in body else None
    amount = validate_amount(body.get("amount")) if "amount" in body else None
    category = (
        validate_string(body.get("category"), "category", max_len=50, required=False) if "category" in body else None
    )
    notes = validate_string(body.get("notes"), "notes", max_len=2000, required=False) if "notes" in body else None
    reference_number = (
        validate_string(body.get("reference_number"), "reference_number", max_len=100, required=False)
        if "reference_number" in body
        else None
    )
    reschedule_due_date = None
    if "due_date" in body:
        reschedule_due_date = validate_date_field(body.get("due_date"), "due_date")
    elif "day_of_month" in body:
        day_of_month = _int_field(body, "day_of_month")
        try:
            reschedule_due_date = resolve_monthly_due_date(user_today(user.timezone), day_of_month)
        except ValueError as exc:
            raise ValidationError(str(exc), details={"field": "day_of_month"})
    elif "annual_month" in body and "annual_day" in body:
        annual_month = _int_field(body, "annual_month")
        annual_day = _int_field(body, "annual_day")
        try:
            reschedule_due_date = resolve_annual_due_date(user_today(user.timezone), annual_month, annual_day)
        except ValueError as exc:
            raise ValidationError(str(exc), details={"field": "annual_month"})

    bill = bill_service.update_bill(
        user,
        bill_id,
        name=name,
        default_amount=amount,
        category=category,
        notes=notes,
        reference_number=reference_number,
        reschedule_due_date=reschedule_due_date,
    )
    return jsonify({"bill": serialize_bill_definition(bill)}), 200


@bp.delete("/<uuid:bill_id>")
def cancel_bill(bill_id):
    user = get_current_user()
    bill = bill_service.cancel_bill(user, bill_id)
    return jsonify({"bill": serialize_bill_definition(bill)}), 200
