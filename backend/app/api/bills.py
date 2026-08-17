import uuid as uuid_module

from flask import Blueprint, jsonify, request

from app.errors import ValidationError, NotFoundError
from app.extensions import db
from app.models import BillStatus, BillDocument
from app.schemas import serialize_bill_definition
from app.services import bill_service
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
    require_fields(body, "name", "amount", "recurrence", "due_date")

    name = validate_string(body.get("name"), "name", min_len=1, max_len=200)
    amount = validate_amount(body.get("amount"))
    recurrence = validate_recurrence(body.get("recurrence"))
    due_date = validate_date_field(body.get("due_date"), "due_date")
    category = validate_string(body.get("category"), "category", max_len=50, required=False)
    notes = validate_string(body.get("notes"), "notes", max_len=2000, required=False)

    bill = bill_service.create_bill(
        user,
        name=name,
        default_amount=amount,
        recurrence=recurrence,
        first_due_date=due_date,
        category=category,
        notes=notes,
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
    reschedule_due_date = (
        validate_date_field(body.get("due_date"), "due_date") if "due_date" in body else None
    )

    bill = bill_service.update_bill(
        user,
        bill_id,
        name=name,
        default_amount=amount,
        category=category,
        notes=notes,
        reschedule_due_date=reschedule_due_date,
    )
    return jsonify({"bill": serialize_bill_definition(bill)}), 200


@bp.delete("/<uuid:bill_id>")
def cancel_bill(bill_id):
    user = get_current_user()
    bill = bill_service.cancel_bill(user, bill_id)
    return jsonify({"bill": serialize_bill_definition(bill)}), 200
