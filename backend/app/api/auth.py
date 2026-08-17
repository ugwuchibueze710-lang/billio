import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from app.extensions import db, limiter
from app.errors import ValidationError, AuthenticationError, ConflictError
from app.models import User, UserSettings, PasswordResetToken, EmailVerificationToken, TokenBlocklist
from app.schemas import serialize_user
from app.utils.security import (
    hash_password,
    verify_password,
    needs_rehash,
    validate_password_strength,
    normalize_username,
    generate_reset_token,
    hash_reset_token,
    get_current_user,
)
from app.utils.validation import (
    get_json_body,
    require_fields,
    validate_string,
    validate_timezone,
    validate_email_optional,
)
from app.services.email import send_password_reset_email, EmailUnavailableError

logger = logging.getLogger("billio.auth")

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _issue_tokens(user: User) -> dict:
    claims = {"tv": user.token_version}
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)
    return {"access_token": access_token, "refresh_token": refresh_token}


@bp.post("/signup")
@limiter.limit(lambda: current_app.config["SIGNUP_RATE_LIMIT"])
def signup():
    body = get_json_body()
    require_fields(body, "first_name", "username", "password", "confirm_password")

    first_name = validate_string(body.get("first_name"), "first_name", min_len=1, max_len=100)
    username = normalize_username(body.get("username"))
    password = body.get("password")
    confirm_password = body.get("confirm_password")
    email = validate_email_optional(body.get("email"))
    tz = body.get("timezone")
    tz = validate_timezone(tz) if tz else "UTC"

    if password != confirm_password:
        raise ValidationError("Passwords do not match.", details={"field": "confirm_password"})
    validate_password_strength(password)

    if User.query.filter(db.func.lower(User.username) == username).first() is not None:
        raise ConflictError("That username is already taken.", error_code="username_taken", details={"field": "username"})

    if email is not None and User.query.filter(db.func.lower(User.email) == email.lower()).first() is not None:
        raise ConflictError("That email is already associated with an account.", error_code="email_taken", details={"field": "email"})

    user = User(
        first_name=first_name,
        username=username,
        email=email,
        password_hash=hash_password(password),
        timezone=tz,
    )
    db.session.add(user)
    db.session.flush()  # obtain user.id before creating dependent row

    settings = UserSettings(user_id=user.id)
    db.session.add(settings)
    db.session.commit()

    logger.info("user_signed_up", extra={"extra_fields": {"user_id": str(user.id)}})

    tokens = _issue_tokens(user)
    return jsonify({"user": serialize_user(user, settings=settings), **tokens}), 201


@bp.post("/login")
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    body = get_json_body()
    require_fields(body, "username", "password")
    username = body.get("username", "").strip().lower()
    password = body.get("password")

    user = User.query.filter(db.func.lower(User.username) == username).first()

    # Constant-shape response whether the username exists or not, to avoid
    # leaking which usernames are registered via timing/response
    # differences. verify_password on a dummy hash keeps timing similar.
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=2$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    password_ok = verify_password(user.password_hash if user else dummy_hash, password)

    if user is None or not password_ok or not user.is_active:
        raise AuthenticationError("Invalid username or password.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.session.commit()

    tokens = _issue_tokens(user)
    logger.info("user_logged_in", extra={"extra_fields": {"user_id": str(user.id)}})
    return jsonify({"user": serialize_user(user, settings=user.settings), **tokens}), 200


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    claims = get_jwt()
    user = User.query.get(identity)
    if user is None or not user.is_active:
        raise AuthenticationError("Session invalid. Please log in again.")
    if claims.get("tv") != user.token_version:
        raise AuthenticationError("Session has expired. Please log in again.")

    access_token = create_access_token(identity=str(user.id), additional_claims={"tv": user.token_version})
    return jsonify({"access_token": access_token}), 200


@bp.post("/logout")
@jwt_required(verify_type=False)
def logout():
    claims = get_jwt()
    jti = claims["jti"]
    token_type = claims.get("type", "access")
    identity = get_jwt_identity()
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)

    db.session.add(TokenBlocklist(jti=jti, token_type=token_type, user_id=identity, expires_at=expires_at))
    db.session.commit()
    return jsonify({"message": "Logged out."}), 200


@bp.get("/me")
def me():
    user = get_current_user()
    return jsonify({"user": serialize_user(user, settings=user.settings)}), 200


@bp.patch("/me")
def update_me():
    user = get_current_user()
    body = get_json_body()

    if "first_name" in body:
        user.first_name = validate_string(body.get("first_name"), "first_name", min_len=1, max_len=100)

    if "timezone" in body:
        user.timezone = validate_timezone(body.get("timezone"))

    if "email" in body:
        new_email = validate_email_optional(body.get("email"))
        if new_email != user.email:
            if new_email is not None:
                existing = User.query.filter(
                    db.func.lower(User.email) == new_email.lower(), User.id != user.id
                ).first()
                if existing is not None:
                    raise ConflictError("That email is already associated with an account.", error_code="email_taken")
            user.email = new_email
            user.email_verified_at = None  # must be re-verified before it's trusted for reset/reminders

    db.session.commit()
    return jsonify({"user": serialize_user(user, settings=user.settings)}), 200


@bp.post("/change-password")
def change_password():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "current_password", "new_password", "confirm_new_password")

    if not verify_password(user.password_hash, body.get("current_password")):
        raise AuthenticationError("Current password is incorrect.")
    if body.get("new_password") != body.get("confirm_new_password"):
        raise ValidationError("New passwords do not match.", details={"field": "confirm_new_password"})
    validate_password_strength(body.get("new_password"))

    user.password_hash = hash_password(body.get("new_password"))
    user.token_version += 1  # invalidates every previously issued token
    db.session.commit()

    tokens = _issue_tokens(user)
    return jsonify({"message": "Password changed. Please use your new session tokens.", **tokens}), 200


@bp.post("/forgot-password")
@limiter.limit(lambda: current_app.config["PASSWORD_RESET_RATE_LIMIT"])
def forgot_password():
    body = get_json_body()
    require_fields(body, "username_or_email")
    identifier = body.get("username_or_email", "").strip().lower()

    user = User.query.filter(
        db.or_(db.func.lower(User.username) == identifier, db.func.lower(User.email) == identifier)
    ).first()

    generic_response = jsonify(
        {"message": "If an account with a verified email matches, a reset link has been sent."}
    ), 200

    if user is None or not user.email or user.email_verified_at is None:
        # Same response either way -- do not reveal account existence or
        # whether the account simply has no email on file.
        return generic_response

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=current_app.config["PASSWORD_RESET_TOKEN_EXPIRES_MINUTES"]
    )
    db.session.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.session.commit()

    reset_url = f"{current_app.config['FRONTEND_BASE_URL']}/reset-password?token={raw_token}"
    try:
        send_password_reset_email(user.email, user.first_name, reset_url)
    except EmailUnavailableError:
        logger.error("password_reset_email_failed", extra={"extra_fields": {"user_id": str(user.id)}})
        # Still return the generic success response -- do not leak delivery
        # failures to the client, and do not block on email infra issues.

    return generic_response


@bp.post("/reset-password")
@limiter.limit(lambda: current_app.config["PASSWORD_RESET_RATE_LIMIT"])
def reset_password():
    body = get_json_body()
    require_fields(body, "token", "new_password", "confirm_new_password")

    if body.get("new_password") != body.get("confirm_new_password"):
        raise ValidationError("Passwords do not match.", details={"field": "confirm_new_password"})
    validate_password_strength(body.get("new_password"))

    token_hash = hash_reset_token(body.get("token"))
    reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at < now
    ):
        raise ValidationError("This reset link is invalid or has expired.", error_code="invalid_reset_token")

    user = User.query.get(reset_token.user_id)
    if user is None or not user.is_active:
        raise ValidationError("This reset link is invalid or has expired.", error_code="invalid_reset_token")

    user.password_hash = hash_password(body.get("new_password"))
    user.token_version += 1
    reset_token.used_at = now
    db.session.commit()

    logger.info("password_reset_completed", extra={"extra_fields": {"user_id": str(user.id)}})
    return jsonify({"message": "Password has been reset. Please log in."}), 200


@bp.post("/verify-email/request")
def request_email_verification():
    user = get_current_user()
    if not user.email:
        raise ValidationError("Add an email address first.")
    if user.email_verified_at is not None:
        return jsonify({"message": "Email is already verified."}), 200

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db.session.add(
        EmailVerificationToken(user_id=user.id, email=user.email, token_hash=token_hash, expires_at=expires_at)
    )
    db.session.commit()

    verify_url = f"{current_app.config['FRONTEND_BASE_URL']}/verify-email?token={raw_token}"
    try:
        import resend

        if current_app.config.get("RESEND_API_KEY"):
            resend.api_key = current_app.config["RESEND_API_KEY"]
            resend.Emails.send(
                {
                    "from": current_app.config["RESEND_FROM_EMAIL"],
                    "to": [user.email],
                    "subject": "Verify your Billio email address",
                    "html": f'<p>Hi {user.first_name},</p><p><a href="{verify_url}">Verify your email</a> to enable password reset by email and email reminders. This link expires in 24 hours.</p>',
                }
            )
    except Exception:
        logger.error("verification_email_failed", extra={"extra_fields": {"user_id": str(user.id)}})
        raise ValidationError("Could not send verification email right now. Please try again shortly.", status_code=502, error_code="upstream_unavailable")

    return jsonify({"message": "Verification email sent."}), 200


@bp.post("/verify-email/confirm")
def confirm_email_verification():
    body = get_json_body()
    require_fields(body, "token")
    token_hash = hash_reset_token(body.get("token"))
    record = EmailVerificationToken.query.filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if record is None or record.used_at is not None or record.expires_at < now:
        raise ValidationError("This verification link is invalid or has expired.")

    user = User.query.get(record.user_id)
    if user is None or user.email != record.email:
        raise ValidationError("This verification link is invalid or has expired.")

    user.email_verified_at = now
    record.used_at = now
    db.session.commit()
    return jsonify({"message": "Email verified."}), 200
