"""
Structured JSON logging. Every request produces one log line with method,
path, status, latency, and outcome. Request/response bodies, headers,
passwords, tokens, and bill contents are never logged -- only metadata.
"""
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

from flask import g, request


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO if not app.debug else logging.DEBUG)

    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO if not app.debug else logging.DEBUG)

    # Quiet noisy third-party loggers unless something goes wrong.
    for noisy in ("werkzeug", "urllib3", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    @app.before_request
    def _start_timer():
        g._request_start = time.monotonic()
        g._request_id = str(uuid.uuid4())

    @app.after_request
    def _log_request(response):
        try:
            duration_ms = round((time.monotonic() - getattr(g, "_request_start", time.monotonic())) * 1000, 2)
            user_id = None
            try:
                # Best-effort only, for log correlation -- deliberately does
                # NOT verify the token's signature (that's get_current_user's
                # job for actual auth decisions). Any failure here just
                # means the log line has no user_id, never a broken request.
                import jwt as pyjwt

                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    claims = pyjwt.decode(auth_header[7:], options={"verify_signature": False})
                    user_id = claims.get("sub")
            except Exception:
                pass
            logging.getLogger("billio.access").info(
                "request_handled",
                extra={
                    "extra_fields": {
                        "request_id": getattr(g, "_request_id", None),
                        "method": request.method,
                        "path": request.path,
                        "status": response.status_code,
                        "duration_ms": duration_ms,
                        "user_id": user_id,
                    }
                },
            )
        except Exception:  # logging must never break a request
            app.logger.exception("failed_to_log_request")
        response.headers["X-Request-Id"] = getattr(g, "_request_id", "")
        return response
