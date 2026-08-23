"""
Thin wrapper around Supabase's Auth REST API (Admin + GoTrue token endpoints).

Billio's own /api/auth/* endpoints are the only thing that ever talks to
Supabase -- the frontend never calls Supabase directly, so its request/
response shapes (and therefore Login.jsx/Signup.jsx/AuthContext/client.js)
never had to change. This module is where every Supabase HTTP call lives.

Only the service_role key is used (never the anon key), because everything
here runs server-side. SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are read
from Flask config, not the environment directly, so tests can override them.
"""
import logging

import jwt as pyjwt
import requests
from flask import current_app

from app.errors import AuthenticationError, ConflictError, UpstreamServiceError, ValidationError

logger = logging.getLogger("billio.supabase")

_REQUEST_TIMEOUT = 10

# PyJWKClient caches the fetched JWKS in-memory and refreshes it lazily, so
# we keep one instance per SUPABASE_URL for the life of the process instead
# of re-fetching the key set on every single request.
_jwk_clients: dict[str, "pyjwt.PyJWKClient"] = {}


class SupabaseAuthError(Exception):
    """Raised for any non-2xx response from Supabase. `status_code` and
    `payload` carry through Supabase's own response for the caller to
    translate into the appropriate ApiError subclass."""

    def __init__(self, status_code: int, payload: dict | str):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Supabase auth request failed ({status_code}): {payload}")


def _base_url() -> str:
    url = current_app.config.get("SUPABASE_URL")
    if not url:
        raise UpstreamServiceError("Authentication is not configured.")
    return url.rstrip("/")


def _service_role_key() -> str:
    key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise UpstreamServiceError("Authentication is not configured.")
    return key


def _headers(*, bearer: str | None = None) -> dict:
    key = _service_role_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {bearer or key}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, bearer: str | None = None, json: dict | None = None, params: dict | None = None) -> dict:
    url = f"{_base_url()}{path}"
    try:
        resp = requests.request(
            method, url, headers=_headers(bearer=bearer), json=json, params=params, timeout=_REQUEST_TIMEOUT
        )
    except requests.RequestException as exc:
        logger.error("supabase_request_failed", exc_info=exc, extra={"extra_fields": {"path": path}})
        raise UpstreamServiceError("Authentication service is unavailable. Please try again.") from exc

    if resp.status_code >= 400:
        try:
            payload = resp.json()
        except ValueError:
            payload = resp.text
        raise SupabaseAuthError(resp.status_code, payload)

    if not resp.content:
        return {}
    try:
        return resp.json()
    except ValueError:
        return {}


# --- Admin API (service_role only) ------------------------------------------------


def admin_create_user(email: str, password: str, user_metadata: dict | None = None) -> dict:
    """Creates a Supabase auth user. `email_confirm: True` marks the user as
    already confirmed, since Billio never uses Supabase's own confirmation
    emails -- our existing Resend-based email-verification flow is kept
    entirely separate and untouched."""
    body = {"email": email, "password": password, "email_confirm": True}
    if user_metadata:
        body["user_metadata"] = user_metadata
    try:
        return _request("POST", "/auth/v1/admin/users", json=body)
    except SupabaseAuthError as exc:
        if exc.status_code in (400, 422):
            message = _extract_message(exc.payload) or "Could not create your account."
            if "already" in message.lower() or "exists" in message.lower():
                raise ConflictError("That email is already associated with an account.", error_code="email_taken")
            raise ValidationError(message)
        logger.error("supabase_create_user_failed", extra={"extra_fields": {"status": exc.status_code}})
        raise UpstreamServiceError("Could not create your account right now. Please try again.")


def admin_update_user(supabase_user_id: str, **fields) -> dict:
    """fields may include password=..., email=..., user_metadata={...}."""
    try:
        return _request("PUT", f"/auth/v1/admin/users/{supabase_user_id}", json=fields)
    except SupabaseAuthError as exc:
        logger.error("supabase_update_user_failed", extra={"extra_fields": {"status": exc.status_code}})
        if exc.status_code in (400, 422):
            raise ValidationError(_extract_message(exc.payload) or "Could not update your account.")
        raise UpstreamServiceError("Could not update your account right now. Please try again.")


def admin_delete_user(supabase_user_id: str) -> None:
    try:
        _request("DELETE", f"/auth/v1/admin/users/{supabase_user_id}")
    except SupabaseAuthError as exc:
        # Best-effort cleanup only -- never block a local account deletion
        # on the remote side failing (mirrors app/services/storage.py's
        # delete_object, which follows the same "log and continue" rule).
        logger.error("supabase_delete_user_failed", extra={"extra_fields": {"status": exc.status_code}})


# --- Token grant endpoints (used for login / refresh / password verification) -----


def sign_in_with_password(email: str, password: str) -> dict:
    """Returns Supabase's token response: access_token, refresh_token,
    expires_in, user. Raises AuthenticationError on bad credentials."""
    try:
        return _request("POST", "/auth/v1/token", params={"grant_type": "password"}, json={"email": email, "password": password})
    except SupabaseAuthError as exc:
        if exc.status_code in (400, 401):
            raise AuthenticationError("Invalid username or password.")
        logger.error("supabase_sign_in_failed", extra={"extra_fields": {"status": exc.status_code}})
        raise UpstreamServiceError("Authentication service is unavailable. Please try again.")


def refresh_access_token(refresh_token: str) -> dict:
    try:
        return _request("POST", "/auth/v1/token", params={"grant_type": "refresh_token"}, json={"refresh_token": refresh_token})
    except SupabaseAuthError as exc:
        if exc.status_code in (400, 401):
            raise AuthenticationError("Session expired. Please log in again.")
        logger.error("supabase_refresh_failed", extra={"extra_fields": {"status": exc.status_code}})
        raise UpstreamServiceError("Authentication service is unavailable. Please try again.")


def sign_out(access_token: str, scope: str = "global") -> None:
    """scope='global' revokes every refresh token for this user (matches
    Billio's old "logout everywhere on password change" behavior); a plain
    logout call still only needs to kill the current session, but using
    'global' here is simpler and safe since Billio doesn't track per-device
    sessions separately."""
    try:
        _request("POST", "/auth/v1/logout", bearer=access_token, params={"scope": scope}, json={})
    except SupabaseAuthError as exc:
        # Logout should never fail the request from the user's point of view
        # -- the frontend clears its local tokens regardless.
        logger.error("supabase_sign_out_failed", extra={"extra_fields": {"status": exc.status_code}})


def _extract_message(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("msg") or payload.get("message") or payload.get("error_description")
    return None


# --- JWT verification (used by get_current_user on every authenticated request) ---


def _jwk_client() -> "pyjwt.PyJWKClient":
    url = _base_url()
    client = _jwk_clients.get(url)
    if client is None:
        client = pyjwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")
        _jwk_clients[url] = client
    return client


def verify_access_token(token: str) -> dict:
    """Verifies a Supabase-issued access token's signature, expiry, issuer
    and audience, and returns its claims. Raises AuthenticationError for any
    invalid/expired/malformed token."""
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=f"{_base_url()}/auth/v1",
        )
    except pyjwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired session. Please log in again.") from exc
    except Exception as exc:
        logger.error("supabase_jwt_verify_failed", exc_info=exc)
        raise UpstreamServiceError("Authentication service is unavailable. Please try again.") from exc
    return claims
