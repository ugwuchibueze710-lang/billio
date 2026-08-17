"""
Password hashing (Argon2id) and auth helper utilities shared across the app.
"""
import re
import secrets
import hashlib
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

from app.errors import AuthorizationError, AuthenticationError, ValidationError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

_COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1",
    "password123", "123456", "qwerty", "qwerty123", "111111", "123123",
    "abc123", "letmein", "monkey", "iloveyou", "admin", "welcome",
    "welcome1", "football", "dragon", "sunshine", "princess", "starwars",
    "master", "hello", "freedom", "whatever", "trustno1", "passw0rd",
    "changeme", "billio", "12345678910",
}

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")


def hash_password(raw_password: str) -> str:
    return _hasher.hash(raw_password)


def verify_password(password_hash: str, raw_password: str) -> bool:
    try:
        return _hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


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


def current_user_id() -> str:
    """Resolve the authenticated user's id from the verified JWT. Never
    trust a client-supplied user_id for any authorization decision."""
    verify_jwt_in_request()
    identity = get_jwt_identity()
    if not identity:
        raise AuthenticationError("Authentication required.")
    return identity


def get_current_user():
    """
    Verify the JWT, load the corresponding user, and additionally check the
    embedded `tv` (token_version) claim against the user's current
    token_version. This means changing a password (which bumps
    token_version) instantly invalidates every previously issued token,
    even ones not individually blocklisted -- important because a stolen
    token should stop working the moment the legitimate user reacts.
    """
    from app.models import User

    verify_jwt_in_request()
    claims = get_jwt()
    identity = get_jwt_identity()
    if not identity:
        raise AuthenticationError("Authentication required.")

    user = User.query.get(identity)
    if user is None or not user.is_active:
        raise AuthenticationError("Authentication required.")

    token_version = claims.get("tv")
    if token_version is None or token_version != user.token_version:
        raise AuthenticationError("Session has expired. Please log in again.")

    return user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user.is_admin:
            raise AuthorizationError("This action requires administrator access.")
        return fn(*args, **kwargs)

    return wrapper
