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

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_ERROR_MESSAGE_KEY = "error"

    # Password reset tokens are short-lived and single-use.
    PASSWORD_RESET_TOKEN_EXPIRES_MINUTES = 30

    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB hard cap on any request body
    MAX_BILL_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB per uploaded bill image
    ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
    MAX_BATCH_UPLOAD_IMAGES = 15

    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_STRATEGY = "fixed-window"

    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute;30 per hour")
    SIGNUP_RATE_LIMIT = os.environ.get("SIGNUP_RATE_LIMIT", "10 per hour")
    FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT", "5 per hour;20 per day")
    AI_RATE_LIMIT = os.environ.get("AI_RATE_LIMIT", "20 per hour")
    PASSWORD_RESET_RATE_LIMIT = os.environ.get("PASSWORD_RESET_RATE_LIMIT", "5 per hour")

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "llama-3.2-90b-vision-preview")
    GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.1-70b-versatile")
    GROQ_TIMEOUT_SECONDS = float(os.environ.get("GROQ_TIMEOUT_SECONDS", "20"))

    RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
    RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Billio <noreply@billio.app>")

    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")  # R2 endpoint
    S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    S3_REGION = os.environ.get("S3_REGION", "auto")

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
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-insecure-jwt-secret-change-me")


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://billio:billio@localhost:5432/billio_test"
    )
    SECRET_KEY = "testing-secret"
    JWT_SECRET_KEY = "testing-jwt-secret"
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"


class ProductionConfig(BaseConfig):
    ENV = "production"

    def __init__(self):
        pass

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")

    @staticmethod
    def init_app(app):
        # Fail fast and loud if production is missing required secrets,
        # rather than silently running with an insecure default.
        for name in ("DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY"):
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
