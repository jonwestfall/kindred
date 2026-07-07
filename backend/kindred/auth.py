"""Authentication, password hashing, and authorization helpers.

Kindred intentionally keeps auth small and local: the administrator account is
provided by environment variables, regular users are stored in SQLite, and API
clients carry short signed bearer tokens. This is enough for a home/LAN MVP
without introducing an external identity provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings


Role = Literal["admin", "user"]
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated request identity."""

    username: str
    role: Role
    user_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def hash_password(password: str, *, iterations: int = 390_000) -> str:
    """Create a PBKDF2 password hash suitable for local account storage."""

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.urlsafe_b64encode(salt).decode()}$"
        f"{base64.urlsafe_b64encode(digest).decode()}"
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification for hashes produced by hash_password."""

    try:
        scheme, iterations_text, salt_text, digest_text = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_text))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64_json(data: str) -> dict[str, Any]:
    padded = data + "=" * (-len(data) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()))


def create_token(principal: Principal, settings: Settings) -> str:
    """Create a signed bearer token without persisting server-side session state."""

    now = int(time.time())
    payload = {
        "sub": principal.username,
        "role": principal.role,
        "uid": principal.user_id,
        "iat": now,
        "exp": now + settings.session_hours * 3600,
    }
    body = _b64_json(payload)
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def parse_token(token: str, settings: Settings) -> Principal:
    """Validate and decode a bearer token."""

    try:
        body, signature_text = token.split(".", 1)
        expected = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode((signature_text + "=" * (-len(signature_text) % 4)).encode())
        if not hmac.compare_digest(actual, expected):
            raise ValueError("bad signature")
        payload = _unb64_json(body)
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        role = payload.get("role")
        if role not in {"admin", "user"}:
            raise ValueError("bad role")
        return Principal(
            username=str(payload["sub"]),
            role=role,
            user_id=payload.get("uid"),
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


def authenticate_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """FastAPI dependency returning the current principal.

    Tests and fully private deployments can set KINDRED_AUTH_ENABLED=false,
    which produces a local admin identity for backwards-compatible automation.
    """

    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return Principal(username="local-admin", role="admin")
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    principal = parse_token(credentials.credentials, settings)
    if principal.is_admin:
        return principal
    user = request.app.state.database.get_user(principal.user_id)
    if not user or user["disabled"]:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return principal


def require_admin(principal: Principal = Depends(authenticate_request)) -> Principal:
    """Require the administrator role."""

    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal


def websocket_token_from_header_or_query(
    authorization: str | None,
    token: str | None,
    settings: Settings,
) -> Principal:
    """Decode identity for WebSocket clients, which cannot set headers reliably."""

    if not settings.auth_enabled:
        return Principal(username="local-admin", role="admin")
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1]
    elif token:
        bearer = token
    if not bearer:
        raise HTTPException(status_code=401, detail="Authentication required")
    return parse_token(bearer, settings)
