from flask import Blueprint, jsonify, request

from app.extensions import db
from app.errors import NotFoundError, ValidationError
from app.models import Feedback, FeedbackStatus, AdminAuditLog
from app.schemas import serialize_feedback
from app.utils.security import admin_required, get_current_user
from app.utils.validation import get_json_body, validate_string, validate_pagination

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _log(action: str, target_type: str, target_id, metadata: dict | None = None):
    user = get_current_user()
    db.session.add(
        AdminAuditLog(actor_user_id=user.id, action=action, target_type=target_type, target_id=target_id, metadata_json=metadata)
    )


@bp.get("/feedback")
@admin_required
def list_feedback():
    type_filter = request.args.get("type")
    status_filter = request.args.get("status")
    search = request.args.get("search")
    sort = request.args.get("sort", "newest")
    page, per_page = validate_pagination(request.args)

    query = Feedback.query

    if type_filter:
        from app.models import FeedbackType

        try:
            query = query.filter_by(type=FeedbackType(type_filter))
        except ValueError:
            raise ValidationError("Invalid type filter.")

    if status_filter:
        try:
            query = query.filter_by(status=FeedbackStatus(status_filter))
        except ValueError:
            raise ValidationError("Invalid status filter.")

    if search:
        query = query.filter(Feedback.message.ilike(f"%{search.strip()}%"))

    query = query.order_by(Feedback.created_at.desc() if sort != "oldest" else Feedback.created_at.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return (
        jsonify(
            {
                "feedback": [serialize_feedback(f, is_admin=True) for f in pagination.items],
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages,
            }
        ),
        200,
    )


@bp.get("/feedback/<uuid:feedback_id>")
@admin_required
def get_feedback(feedback_id):
    feedback = Feedback.query.get(feedback_id)
    if feedback is None:
        raise NotFoundError("Feedback not found.")
    _log("feedback.viewed", "feedback", feedback.id)
    db.session.commit()
    return jsonify({"feedback": serialize_feedback(feedback, is_admin=True)}), 200


@bp.patch("/feedback/<uuid:feedback_id>")
@admin_required
def update_feedback(feedback_id):
    feedback = Feedback.query.get(feedback_id)
    if feedback is None:
        raise NotFoundError("Feedback not found.")

    body = get_json_body()
    changes = {}

    if "status" in body:
        try:
            new_status = FeedbackStatus(body["status"])
        except ValueError:
            raise ValidationError(f"status must be one of: {', '.join(s.value for s in FeedbackStatus)}")
        if new_status != feedback.status:
            changes["old_status"] = feedback.status.value
            changes["new_status"] = new_status.value
            feedback.status = new_status

    if "admin_note" in body:
        note = validate_string(body.get("admin_note"), "admin_note", max_len=5000, required=False)
        feedback.admin_note = note
        changes["admin_note_updated"] = True

    if changes:
        _log("feedback.updated", "feedback", feedback.id, metadata=changes)

    db.session.commit()
    return jsonify({"feedback": serialize_feedback(feedback, is_admin=True)}), 200
