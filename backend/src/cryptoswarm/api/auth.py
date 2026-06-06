"""Session-cookie auth for the dashboard."""
from __future__ import annotations

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.hash import bcrypt
from fastapi import Request, HTTPException
from functools import lru_cache

_SESSION_COOKIE = "cs_session"
_SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours


@lru_cache(maxsize=1)
def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="dashboard-session")


def make_session_token(username: str, secret: str) -> str:
    return _serializer(secret).dumps({"u": username})


def verify_session_token(token: str, secret: str) -> str | None:
    """Return username if valid, None otherwise."""
    try:
        data = _serializer(secret).loads(token, max_age=_SESSION_MAX_AGE)
        return data.get("u")
    except (BadSignature, SignatureExpired):
        return None


def check_password(plain: str, stored: str) -> bool:
    """Compare plain password against stored (plain-text comparison for simplicity)."""
    return plain == stored


def require_auth(request: Request) -> str:
    """Dependency: returns username or raises 401."""
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from cryptoswarm.config.settings import get_settings
    cfg = get_settings()
    username = verify_session_token(token, cfg.dashboard_secret_key)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired")
    return username
