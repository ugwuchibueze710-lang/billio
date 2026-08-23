"""
Auth helper utilities shared across the app. Credentials themselves are
owned by Supabase Auth (see app.services.supabase_admin) -- this module
verifies the Supabase-issued access token on every request and lazily syncs
the corresponding local `User` row, plus password-strength/username
validation that still runs locally before we ever call Supabase.
"""
import re
import secrets
import hashlib
from functools import wraps

from flask import request

from app.errors import AuthorizationError, AuthenticationError, ValidationError

_COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1",
    "password123", "123456", "qwerty", "qwerty123", "111111", "123123",
    "abc123", "letmein", "monkey", "iloveyou", "admin", "welcome",
    "welcome1", "football", "dragon", "sunshine", "princess", "starwars",
    "master", "hello", "freedom", "whatever", "trustno1", "passw0rd",
    "changeme", "billio", "12345678910",
}

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")


def validate_password_strength(raw_password: str) -> None:
    if not isinstance(raw_password, str) or len(raw_password) < 8:
        raise ValidationError("Password must be at least 8 characters long.", details={"field": "password"})
    if len(raw_password) > 128:
        raise ValidationError("Password is too long.", details={"field": "password"})
    if raw_password.lower() in _COMMON_PASSWORDS:
        raise ValidationError(
            "This password is too common. Please choose a stronger password.", details={"field": "password"}
        )
    if raw_password.isdigit():
        raise ValidationError(
            "Password cannot be all numbers. Please choose a stronger password.", details={"field": "password"}
        )
    # Require at least two character classes for a minimally stronger password.
    classes = sum(
        bool(re.search(pattern, raw_password))
        for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^a-zA-Z0-9]")
    )
    if classes < 2:
        raise ValidationError(
            "Password must include at least two of: lowercase, uppercase, numbers, symbols.",
            details={"field": "password"},
        )


def normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValidationError("Username is required.", details={"field": "username"})
    normalized = username.strip().lower()
    if not USERNAME_RE.match(normalized):
        raise ValidationError(
            "Username must be 3-30 characters and contain only lowercase letters, numbers, and underscores.",
            details={"field": "username"},
        )
    return normalized


def generate_reset_token() -> tuple[str, str]:
    """Returns (raw_token_for_email, sha256_hash_for_storage)."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def bearer_token() -> str:
    """Extracts the raw bearer token from the Authorization header. Used
    both for verified-user auth (get_current_user) and for the /refresh and
    /logout endpoints, which forward a Supabase access/refresh token
    through to Supabase itself rather than verifying it locally."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or len(auth_header) <= 7:
        raise AuthenticationError("Authentication required.")
    return auth_header[7:]


def get_current_user():
    """
    Verify the Supabase access token attached to this request (signature,
    expiry, issuer, audience -- see supabase_admin.verify_access_token),
    then resolve the matching local `User` row by `supabase_user_id`.

    Kept as the single source of truth every endpoint calls -- its external
    contract (verify auth, return a local User ORM object, raise
    AuthenticationError otherwise) is unchanged from before the Supabase
    migration, which is what let every endpoint file outside auth.py/
    account.py stay untouched.
    """
    from app.models import User
    from app.services.supabase_admin import verify_access_token

    token = bearer_token()
    claims = verify_access_token(token)
    supabase_user_id = claims.get("sub")
    if not supabase_user_id:
        raise AuthenticationError("Authentication required.")

    user = User.query.filter_by(supabase_user_id=supabase_user_id).first()
    if user is None or not user.is_active:
        raise AuthenticationError("Authentication required.")

    return user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user.is_admin:
            raise AuthorizationError("This action requires administrator access.")
        return fn(*args, **kwargs)

    return wrapper
