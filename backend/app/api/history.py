from flask import Blueprint, jsonify, request

from app.schemas import serialize_occurrence
from app.services import bill_service, history_service
from app.utils.security import get_current_user
from app.utils.validation import validate_date_field, validate_pagination

bp = Blueprint("history", __name__, url_prefix="/api/history")


@bp.get("")
def history():
    user = get_current_user()

    month = request.args.get("month")
    if month:
        date_from, date_to = history_service.parse_month(month)
    else:
        date_from = validate_date_field(request.args.get("from"), "from") if request.args.get("from") else None
        date_to = validate_date_field(request.args.get("to"), "to") if request.args.get("to") else None

    status = request.args.get("status")
    category = request.args.get("category")
    page, per_page = validate_pagination(request.args)

    query = bill_service.query_occurrences(
        user, status=status, category=category, date_from=date_from, date_to=date_to
    ).order_by(None)
    from app.models import BillOccurrence

    query = query.order_by(BillOccurrence.due_date.desc())

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


@bp.get("/months")
def months():
    user = get_current_user()
    return jsonify({"months": history_service.list_available_months(user)}), 200


@bp.get("/summary")
def summary():
    user = get_current_user()
    month = request.args.get("month")
    if not month:
        from app.errors import ValidationError

        raise ValidationError("month (YYYY-MM) query parameter is required.")
    data = history_service.month_summary(user, month)
    return (
        jsonify(
            {
                "month": data["month"],
                "expected_total": str(data["expected_total"]),
                "paid_total": str(data["paid_total"]),
                "outstanding_total": str(data["outstanding_total"]),
                "bill_count": data["bill_count"],
                "paid_count": data["paid_count"],
            }
        ),
        200,
    )
