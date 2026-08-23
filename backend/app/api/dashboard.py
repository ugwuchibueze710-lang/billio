from flask import Blueprint, jsonify

from app.schemas import serialize_occurrence
from app.services import dashboard_service
from app.utils.security import get_current_user

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("")
def dashboard():
    user = get_current_user()
    data = dashboard_service.get_dashboard(user)

    def ser(occ, bill):
        return serialize_occurrence(occ, user_tz=user.timezone, bill_name=bill.name, category=bill.category)

    next_upcoming = None
    if data["next_upcoming"] is not None:
        occ, bill = data["next_upcoming"]
        next_upcoming = ser(occ, bill)

    return (
        jsonify(
            {
                "caught_up": data["caught_up"],
                "attention_count": data["attention_count"],
                "outstanding_total": str(data["outstanding_total"]),
                "monthly_recurring_total": str(data["monthly_recurring_total"]),
                "urgent": [ser(occ, bill) for occ, bill in data["urgent"]],
                "upcoming": [ser(occ, bill) for occ, bill in data["upcoming"]],
                "recently_paid": [ser(occ, bill) for occ, bill in data["recently_paid"]],
                "next_upcoming": next_upcoming,
            }
        ),
        200,
    )
