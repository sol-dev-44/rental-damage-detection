from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token embedding user_id, tenant_id, and role."""
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TokenPayload:
    """Decoded JWT token payload."""

    def __init__(self, user_id: UUID, tenant_id: UUID, role: str, exp: datetime):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.exp = exp


def verify_token(token: str) -> TokenPayload:
    """
    Decode and verify a JWT token.

    Raises JWTError if the token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])
        role: str = payload["role"]
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        return TokenPayload(user_id=user_id, tenant_id=tenant_id, role=role, exp=exp)
    except (JWTError, KeyError, ValueError) as exc:
        raise JWTError("Could not validate token") from exc
