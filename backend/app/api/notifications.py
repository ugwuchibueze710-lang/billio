import hmac
import logging

from flask import Blueprint, jsonify, request, current_app

from app.extensions import db
from app.errors import ValidationError, AuthenticationError
from app.models import PushSubscription
from app.utils.security import get_current_user
from app.utils.validation import get_json_body, require_fields

logger = logging.getLogger("billio.notifications")

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("/vapid-public-key")
def vapid_public_key():
    key = current_app.config.get("VAPID_PUBLIC_KEY")
    if not key:
        return jsonify({"available": False, "public_key": None}), 200
    return jsonify({"available": True, "public_key": key}), 200


@bp.post("/push-subscription")
def register_push_subscription():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "endpoint", "keys")
    keys = body.get("keys") or {}
    require_fields(keys, "p256dh", "auth")

    endpoint = body.get("endpoint")
    if not isinstance(endpoint, str) or len(endpoint) > 2000:
        raise ValidationError("Invalid push subscription endpoint.")

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing is not None:
        if existing.user_id != user.id:
            # Endpoint reassigned to a different account (e.g. shared device,
            # different user logged in) -- replace ownership safely.
            existing.user_id = user.id
        existing.p256dh = keys.get("p256dh")
        existing.auth = keys.get("auth")
        existing.user_agent = request.headers.get("User-Agent", "")[:255]
        db.session.commit()
        return jsonify({"message": "Push subscription updated.", "id": str(existing.id)}), 200

    subscription = PushSubscription(
        user_id=user.id,
        endpoint=endpoint,
        p256dh=keys.get("p256dh"),
        auth=keys.get("auth"),
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    db.session.add(subscription)
    db.session.commit()
    return jsonify({"message": "Push subscription registered.", "id": str(subscription.id)}), 201


@bp.delete("/push-subscription")
def remove_push_subscription():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "endpoint")
    PushSubscription.query.filter_by(endpoint=body.get("endpoint"), user_id=user.id).delete()
    db.session.commit()
    return jsonify({"message": "Push subscription removed."}), 200


@bp.post("/run-scheduler")
def run_scheduler_http():
    """
    Optional HTTP fallback trigger for the reminder scan, for deployment
    setups that prefer an HTTP-based cron caller over Render's native
    Cron Job (which should instead run `flask send-reminders` directly --
    see README). Protected by a constant-time comparison against
    NOTIFICATION_SCHEDULER_TOKEN; disabled entirely if that token isn't set.
    """
    configured_token = current_app.config.get("NOTIFICATION_SCHEDULER_TOKEN")
    if not configured_token:
        raise AuthenticationError("This endpoint is not enabled.")

    provided = request.headers.get("X-Scheduler-Token", "")
    if not hmac.compare_digest(provided, configured_token):
        raise AuthenticationError("Invalid scheduler token.")

    from app.services.reminder_scheduler import run_reminder_scan

    stats = run_reminder_scan()
    return jsonify({"message": "Reminder scan complete.", "stats": stats}), 200
