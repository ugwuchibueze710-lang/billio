import logging

from flask import Flask, jsonify

from app.config import get_config
from app.extensions import db, migrate, cors, limiter
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
