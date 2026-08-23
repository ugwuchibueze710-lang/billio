from flask import Blueprint, jsonify, request

from app.errors import ValidationError
from app.schemas import serialize_occurrence
from app.services import bill_service
from app.utils.security import get_current_user
from app.utils.validation import validate_date_field, validate_pagination

bp = Blueprint("occurrences", __name__, url_prefix="/api/occurrences")

VALID_STATUSES = {"upcoming", "due_today", "overdue", "paid", "unpaid"}


@bp.get("")
def list_occurrences():
    user = get_current_user()
    status = request.args.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValidationError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    category = request.args.get("category")
    date_from = validate_date_field(request.args.get("from"), "from") if request.args.get("from") else None
    date_to = validate_date_field(request.args.get("to"), "to") if request.args.get("to") else None
    page, per_page = validate_pagination(request.args)

    query = bill_service.query_occurrences(
        user, status=status, category=category, date_from=date_from, date_to=date_to
    )
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = [
        serialize_occurrence(occ, user_tz=user.timezone, bill_name=bill.name, category=bill.category)
        for occ, bill in pagination.items
    ]
    return (
        jsonify(
            {
                "occurrences": items,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages,
            }
        ),
        200,
    )


@bp.get("/<uuid:occurrence_id>")
def get_occurrence(occurrence_id):
    user = get_current_user()
    occurrence = bill_service.get_owned_occurrence(user, occurrence_id)
    bill = occurrence.bill_definition
    return jsonify({"occurrence": serialize_occurrence(occurrence, user_tz=user.timezone, bill_name=bill.name, category=bill.category)}), 200


@bp.post("/<uuid:occurrence_id>/mark-paid")
def mark_paid(occurrence_id):
    user = get_current_user()
    occurrence, new_occurrence, payment = bill_service.mark_occurrence_paid(user, occurrence_id)
    bill = occurrence.bill_definition

    response = {
        "occurrence": serialize_occurrence(occurrence, user_tz=user.timezone, bill_name=bill.name, category=bill.category),
    }
    if new_occurrence is not None:
        response["next_occurrence"] = serialize_occurrence(
            new_occurrence, user_tz=user.timezone, bill_name=bill.name, category=bill.category
        )
    return jsonify(response), 200
