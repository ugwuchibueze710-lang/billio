from flask import Blueprint, jsonify, current_app

from app.extensions import db, limiter
from app.errors import NotFoundError, AuthorizationError
from app.models import Feedback
from app.schemas import serialize_feedback
from app.utils.security import get_current_user
from app.utils.validation import get_json_body, require_fields, validate_string, validate_feedback_type, validate_rating

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@bp.post("")
@limiter.limit(lambda: current_app.config["FEEDBACK_RATE_LIMIT"])
def submit_feedback():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "type", "message")

    feedback_type = validate_feedback_type(body.get("type"))
    message = validate_string(body.get("message"), "message", min_len=1, max_len=5000)
    rating = validate_rating(body.get("rating"))

    feedback = Feedback(user_id=user.id, type=feedback_type, message=message, rating=rating)
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"message": "Thanks. Your feedback has been received.", "feedback": serialize_feedback(feedback)}), 201


@bp.get("")
def list_my_feedback():
    user = get_current_user()
    items = Feedback.query.filter_by(user_id=user.id).order_by(Feedback.created_at.desc()).limit(100).all()
    return jsonify({"feedback": [serialize_feedback(f) for f in items]}), 200


@bp.get("/<uuid:feedback_id>")
def get_my_feedback(feedback_id):
    user = get_current_user()
    feedback = Feedback.query.filter_by(id=feedback_id).first()
    if feedback is None:
        raise NotFoundError("Feedback not found.")
    if feedback.user_id != user.id:
        raise AuthorizationError("You do not have access to this feedback.")
    return jsonify({"feedback": serialize_feedback(feedback)}), 200
