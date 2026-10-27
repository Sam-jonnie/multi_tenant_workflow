import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import TokenType
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenPair,
)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    def register(self, data: RegisterRequest) -> User:
        email = data.email.lower()
        username = data.username.lower()

        if self.users.get_by_email(email):
            raise ConflictError("EMAIL_ALREADY_EXISTS", "Email is already registered.")
        if self.users.get_by_username(username):
            raise ConflictError("USERNAME_ALREADY_EXISTS", "Username is already taken.")

        user = User(
            email=email,
            username=username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )
        try:
            self.users.add(user)
            self.db.commit()
        except IntegrityError:  # two simultaneous registrations; the DB constraint wins
            self.db.rollback()
            raise ConflictError("USER_ALREADY_EXISTS", "User already exists.") from None
        return user

    def login(self, data: LoginRequest) -> TokenPair:
        user = self.users.get_by_email(data.email.lower())
        if user is None:
            verify_password(data.password, DUMMY_HASH)  # constant-ish time
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password.")
        if not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password.")
        if not user.is_active:
            raise ForbiddenError("USER_INACTIVE", "Your account is deactivated.")

        pair = self._issue_tokens(user)
        self.db.commit()
        return pair

    def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, TokenType.REFRESH)
        stored = self.tokens.get_by_jti(payload["jti"])
        if stored is None:
            raise UnauthorizedError("TOKEN_INVALID", "Token is invalid.")

        if stored.revoked_at is not None:
            # An already-used token came back: assume theft, kill the whole family.
            self.tokens.revoke_family(stored.family_id)
            self.db.commit()
            raise UnauthorizedError("TOKEN_REUSED", "Token reuse detected. Please log in again.")

        user = self.users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise ForbiddenError("USER_INACTIVE", "Your account is deactivated.")

        self.tokens.revoke(stored)  # rotation: old token dies
        pair = self._issue_tokens(user, family_id=stored.family_id)
        self.db.commit()
        return pair

    def logout(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token, TokenType.REFRESH)
        stored = self.tokens.get_by_jti(payload["jti"])
        if stored is not None and stored.revoked_at is None:
            self.tokens.revoke(stored)
            self.db.commit()

    def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.hashed_password):
            raise BadRequestError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
        if data.current_password == data.new_password:
            raise BadRequestError("PASSWORD_UNCHANGED", "New password must be different.")

        user.hashed_password = hash_password(data.new_password)
        self.tokens.revoke_all_for_user(user.id)  # log out every device
        self.db.commit()

    def _issue_tokens(self, user: User, family_id: str | None = None) -> TokenPair:
        family_id = family_id or uuid.uuid4().hex
        access = create_access_token(user.id)
        refresh, jti, expires_at = create_refresh_token(user.id)
        self.tokens.add(
            RefreshToken(jti=jti, family_id=family_id, user_id=user.id, expires_at=expires_at)
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )