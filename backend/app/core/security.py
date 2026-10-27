import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import UnauthorizedError

_password_hash = PasswordHash.recommended()
# Used to burn the same time when the email doesn't exist (prevents timing attacks)
DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)


def _encode(user_id: int, token_type: TokenType, expires_at: datetime, jti: str) -> str:
    payload = {
        "sub": str(user_id),  # JWT spec: subject must be a string
        "type": token_type.value,
        "jti": jti,  # unique token id
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return _encode(user_id, TokenType.ACCESS, expires_at, uuid.uuid4().hex)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at). The jti is stored in the DB."""
    jti = uuid.uuid4().hex
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return _encode(user_id, TokenType.REFRESH, expires_at, jti), jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("TOKEN_EXPIRED", "Token has expired.") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("TOKEN_INVALID", "Token is invalid.") from None

    if payload["type"] != expected_type.value:
        raise UnauthorizedError("TOKEN_TYPE_INVALID", "Wrong token type.")
    return payload