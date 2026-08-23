"""
Web Push notifications (VAPID). This is what makes Billio's PWA behave like
a native app with lock-screen-style reminders. A dead/expired subscription
(410 Gone / 404) is removed automatically so the scheduler doesn't keep
retrying it forever.
"""
import json
import logging

from pywebpush import webpush, WebPushException
from flask import current_app

from app.extensions import db
from app.models import PushSubscription

logger = logging.getLogger("billio.push")


class PushUnavailableError(Exception):
    pass


def send_push_to_subscription(subscription: PushSubscription, payload: dict) -> bool:
    """Returns True if delivered, False if the subscription was dead and
    has been removed."""
    cfg = current_app.config
    if not cfg.get("VAPID_PRIVATE_KEY") or not cfg.get("VAPID_PUBLIC_KEY"):
        raise PushUnavailableError("Push notifications are not configured.")

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=cfg["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": cfg["VAPID_SUBJECT"]},
            ttl=86400,
        )
        return True
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (404, 410):
            logger.info("push_subscription_expired", extra={"extra_fields": {"subscription_id": str(subscription.id)}})
            db.session.delete(subscription)
            db.session.commit()
            return False
        logger.error("push_send_failed", exc_info=exc)
        raise PushUnavailableError("Failed to send push notification.") from exc


def send_push_to_user(user, payload: dict) -> int:
    """Sends to every registered device for the user. Returns count delivered."""
    subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
    delivered = 0
    for sub in subscriptions:
        try:
            if send_push_to_subscription(sub, payload):
                delivered += 1
        except PushUnavailableError:
            continue
    return delivered
