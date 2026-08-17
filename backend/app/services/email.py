"""
Transactional email via Resend. All sends are best-effort from the caller's
perspective (callers decide whether a failure should be surfaced) but every
failure is logged with context, never with the email body/recipient PII
beyond what's necessary for debugging.
"""
import logging

import resend
from flask import current_app

logger = logging.getLogger("billio.email")


class EmailUnavailableError(Exception):
    pass


def _client_configured() -> bool:
    return bool(current_app.config.get("RESEND_API_KEY"))


def send_password_reset_email(to_email: str, first_name: str, reset_url: str) -> None:
    if not _client_configured():
        logger.warning("email_not_configured", extra={"extra_fields": {"template": "password_reset"}})
        raise EmailUnavailableError("Email delivery is not configured.")

    resend.api_key = current_app.config["RESEND_API_KEY"]
    try:
        resend.Emails.send(
            {
                "from": current_app.config["RESEND_FROM_EMAIL"],
                "to": [to_email],
                "subject": "Reset your Billio password",
                "html": (
                    f"<p>Hi {_escape(first_name)},</p>"
                    f"<p>We received a request to reset your Billio password. "
                    f'This link expires in 30 minutes and can only be used once.</p>'
                    f'<p><a href="{reset_url}">Reset your password</a></p>'
                    f"<p>If you didn't request this, you can safely ignore this email "
                    f"&mdash; your password will not be changed.</p>"
                    f"<p>&mdash; Billio</p>"
                ),
            }
        )
    except Exception as exc:  # Resend SDK raises various exception types
        logger.error("email_send_failed", extra={"extra_fields": {"template": "password_reset"}}, exc_info=exc)
        raise EmailUnavailableError("Failed to send password reset email.") from exc


def send_bill_reminder_email(to_email: str, first_name: str, bill_name: str, amount: str, due_label: str, deep_link_url: str, private: bool) -> None:
    if not _client_configured():
        logger.warning("email_not_configured", extra={"extra_fields": {"template": "bill_reminder"}})
        raise EmailUnavailableError("Email delivery is not configured.")

    resend.api_key = current_app.config["RESEND_API_KEY"]
    if private:
        subject = "You have a bill reminder"
        body = f"<p>Hi {_escape(first_name)},</p><p>You have a bill {due_label}. Open Billio for details.</p>"
    else:
        subject = f"{bill_name}: {due_label}"
        body = (
            f"<p>Hi {_escape(first_name)},</p>"
            f"<p><strong>{_escape(bill_name)}</strong> &mdash; ${amount} {due_label}.</p>"
            f'<p><a href="{deep_link_url}">View this bill</a></p>'
        )
    try:
        resend.Emails.send(
            {
                "from": current_app.config["RESEND_FROM_EMAIL"],
                "to": [to_email],
                "subject": subject,
                "html": body,
            }
        )
    except Exception as exc:
        logger.error("email_send_failed", extra={"extra_fields": {"template": "bill_reminder"}}, exc_info=exc)
        raise EmailUnavailableError("Failed to send reminder email.") from exc


def _escape(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
