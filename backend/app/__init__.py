import logging

from flask import Flask, jsonify

from app.config import get_config
from app.extensions import db, migrate, jwt, cors, limiter
from app.errors import register_error_handlers
from app.logging_config import configure_logging


def create_app(config_object=None):
    app = Flask(__name__)
    config_object = config_object or get_config()
    app.config.from_object(config_object)
    if hasattr(config_object, "init_app"):
        config_object.init_app(app)

    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # CORS: explicit allow-list only. An empty CORS_ORIGINS in production
    # means no cross-origin browser access is permitted, rather than
    # silently falling back to a wildcard.
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", [])}},
        supports_credentials=False,
        methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    register_error_handlers(app)
    _register_security_headers(app)
    _register_jwt_callbacks(app)

    from app.api import register_blueprints

    register_blueprints(app)

    from app.cli import register_cli

    register_cli(app)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    return app


def _register_security_headers(app: Flask):
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if app.config["ENV"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        # The API returns JSON only -- a strict CSP mainly guards against
        # this backend ever accidentally serving HTML with an XSS vector.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


def _register_jwt_callbacks(app: Flask):
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from app.models import TokenBlocklist

        jti = jwt_payload["jti"]
        return db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": {"code": "token_expired", "message": "Session expired. Please log in again."}}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": {"code": "invalid_token", "message": "Invalid authentication token."}}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"error": {"code": "authentication_required", "message": "Authentication required."}}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": {"code": "token_revoked", "message": "Session has been revoked. Please log in again."}}), 401
