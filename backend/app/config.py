"""
Environment-based configuration for Billio.

Every secret and environment-dependent value is read from the environment.
Nothing sensitive is ever hardcoded here. See .env.example for the full
list of variables a deployment must supply.
"""
import os
from datetime import timedelta


def _require(name: str) -> str:
    """Fetch a required environment variable or raise a clear startup error."""
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"See .env.example for the full list of required configuration."
        )
    return value


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    ENV = "base"
    DEBUG = False
    TESTING = False

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Password reset tokens are short-lived and single-use.
    PASSWORD_RESET_TOKEN_EXPIRES_MINUTES = 30

    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB hard cap on any request body
    MAX_BILL_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB per uploaded bill photo/PDF
    # No format allow-list here -- app/services/image_validation.py accepts
    # any picture format Pillow can genuinely decode (see its docstring) and
    # normalizes everything to PNG, rather than gating on a fixed list.
    MAX_BATCH_UPLOAD_IMAGES = 15

    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"

    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute;30 per hour")
    SIGNUP_RATE_LIMIT = os.environ.get("SIGNUP_RATE_LIMIT", "10 per hour")
    FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT", "5 per hour;20 per day")
    AI_RATE_LIMIT = os.environ.get("AI_RATE_LIMIT", "20 per hour")
    PASSWORD_RESET_RATE_LIMIT = os.environ.get("PASSWORD_RESET_RATE_LIMIT", "5 per hour")

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    # Groq's model catalog changes over time -- these were current as of
    # August 2026. If extraction/parsing start failing with a "model
    # decommissioned" or "model not found" error, check
    # https://console.groq.com/docs/models for current model IDs and
    # update GROQ_VISION_MODEL / GROQ_TEXT_MODEL (env vars, no code change
    # needed).
    GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
    GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "openai/gpt-oss-20b")
    GROQ_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "20"))

    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Billio <noreply@billio.app>")

    # Supabase Auth (and, via the same project, Supabase Storage -- see the
    # S3_* settings below). Only the service_role key is used; it never
    # reaches the frontend, since only this backend talks to Supabase.
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    # Object storage for uploaded bill photos/PDFs -- points at Supabase
    # Storage's S3-compatible endpoint (https://<project_ref>.storage.supabase.co/storage/v1/s3),
    # using the separate "S3 Access Key ID / Secret Access Key" pair
    # generated on the Storage settings page (NOT the anon/service_role
    # Auth keys). Any other S3-compatible provider (R2, Backblaze) also
    # works here without code changes -- only these env vars change.
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_REGION = os.environ.get("S3_REGION", "auto")
    # Supabase (and most non-AWS S3-compatible providers) require
    # path-style addressing (bucket in the URL path, not as a subdomain).
    S3_ADDRESSING_STYLE = os.environ.get("S3_ADDRESSING_STYLE", "path")

    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:support@billio.app")

    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

    FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")

    NOTIFICATION_SCHEDULER_TOKEN = os.environ.get("NOTIFICATION_SCHEDULER_TOKEN")

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://billio:billio@localhost:5432/billio_dev"
    )
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://billio:billio@localhost:5432/billio_test"
    )
    SECRET_KEY = "testing-secret"
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"


class ProductionConfig(BaseConfig):
    ENV = "production"

    def __init__(self):
        pass

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    @staticmethod
    def init_app(app):
        # Fail fast and loud if production is missing required secrets,
        # rather than silently running with an insecure default.
        for name in ("DATABASE_URL", "SECRET_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
            if not os.environ.get(name):
                raise RuntimeError(f"Missing required production environment variable: {name}")
        # SQLAlchemy 1.4+/2.0 requires the postgresql:// scheme, not postgres://
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
            app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace(
                "postgres://", "postgresql://", 1
            )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
