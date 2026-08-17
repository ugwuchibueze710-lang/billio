"""
Central error handling. Every error response is structured JSON:
{"error": {"code": "...", "message": "..."}} with an appropriate HTTP
status. Internal exception details (stack traces, SQL errors, etc.) are
logged server-side but never leaked to the client.
"""
import logging

from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("billio.errors")


class ApiError(Exception):
    """Base class for application errors that should surface to the client
    with a specific status code and machine-readable error code."""

    status_code = 400
    error_code = "bad_request"

    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class ValidationError(ApiError):
    status_code = 422
    error_code = "validation_error"


class AuthenticationError(ApiError):
    status_code = 401
    error_code = "authentication_error"


class AuthorizationError(ApiError):
    status_code = 403
    error_code = "authorization_error"


class NotFoundError(ApiError):
    status_code = 404
    error_code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    error_code = "conflict"


class RateLimitedError(ApiError):
    status_code = 429
    error_code = "rate_limited"


class UpstreamServiceError(ApiError):
    """Used when a third-party dependency (Groq, Resend, R2, ...) fails.
    Never exposes upstream error details to the client."""

    status_code = 502
    error_code = "upstream_unavailable"


def _error_response(status_code: int, error_code: str, message: str, details=None):
    body = {"error": {"code": error_code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status_code


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        if err.status_code >= 500:
            logger.error("api_error", extra={"extra_fields": {"error_code": err.error_code}})
        return _error_response(err.status_code, err.error_code, err.message, err.details)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return _error_response(err.code or 500, err.name.lower().replace(" ", "_"), err.description or err.name)

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(err: SQLAlchemyError):
        logger.error("database_error", exc_info=err)
        return _error_response(503, "database_unavailable", "A database error occurred. Please try again.")

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        logger.error("unhandled_exception", exc_info=err)
        return _error_response(500, "internal_error", "An unexpected error occurred. Please try again.")
