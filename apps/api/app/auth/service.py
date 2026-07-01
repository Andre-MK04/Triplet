from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.email import build_email_provider
from app.auth.schemas import AuthUserResponse, SignupRequest, UpdateProfileRequest
from app.auth.oauth import OAuthProfile
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    hash_password,
    hash_token,
    new_uuid,
    unusable_password_hash,
    validate_password_strength,
    verify_password,
)
from app.config import settings
from app.db.models import PasswordResetTokenDB, RefreshTokenSessionDB, UserDB, UserOAuthAccountDB


class AuthError(ValueError):
    pass


class DuplicateEmailError(AuthError):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def signup(self, request: SignupRequest, user_agent: str | None = None, ip_address: str | None = None):
        password_error = validate_password_strength(request.password, request.email)
        if password_error:
            raise AuthError(password_error)
        existing = self.db.scalar(select(UserDB).where(UserDB.email == request.email))
        if existing:
            raise DuplicateEmailError("An account with this email already exists.")
        user = UserDB(
            id=new_uuid(),
            email=request.email,
            password_hash=hash_password(request.password),
            display_name=request.displayName,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        self.db.flush()
        access_token, refresh_token = self._create_session(user, user_agent, ip_address)
        self.db.commit()
        self.db.refresh(user)
        return user, access_token, refresh_token

    def login(self, email: str, password: str, user_agent: str | None = None, ip_address: str | None = None):
        user = self.db.scalar(select(UserDB).where(UserDB.email == email.strip().lower()))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password")
        user.last_login_at = datetime.utcnow()
        access_token, refresh_token = self._create_session(user, user_agent, ip_address)
        self.db.commit()
        self.db.refresh(user)
        return user, access_token, refresh_token

    def login_with_oauth(
        self,
        profile: OAuthProfile,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ):
        account = self.db.scalar(
            select(UserOAuthAccountDB).where(
                UserOAuthAccountDB.provider == profile.provider,
                UserOAuthAccountDB.provider_user_id == profile.provider_user_id,
            )
        )
        if account:
            user = account.user
            if not user.is_active:
                raise AuthError("Account is disabled.")
            account.email = profile.email
            account.updated_at = datetime.utcnow()
        else:
            user = self.db.scalar(select(UserDB).where(UserDB.email == profile.email))
            if not user:
                user = UserDB(
                    id=new_uuid(),
                    email=profile.email,
                    password_hash=unusable_password_hash(),
                    display_name=profile.display_name,
                    is_active=True,
                    is_verified=profile.email_verified,
                )
                self.db.add(user)
                self.db.flush()
            elif profile.email_verified and not user.is_verified:
                user.is_verified = True

            account = UserOAuthAccountDB(
                id=new_uuid(),
                user_id=user.id,
                provider=profile.provider,
                provider_user_id=profile.provider_user_id,
                email=profile.email,
            )
            self.db.add(account)

        if profile.display_name and not user.display_name:
            user.display_name = profile.display_name
        user.last_login_at = datetime.utcnow()
        access_token, refresh_token = self._create_session(user, user_agent, ip_address)
        self.db.commit()
        self.db.refresh(user)
        return user, access_token, refresh_token

    def refresh(self, raw_refresh_token: str, user_agent: str | None = None, ip_address: str | None = None):
        session = self.db.scalar(
            select(RefreshTokenSessionDB).where(RefreshTokenSessionDB.token_hash == hash_token(raw_refresh_token))
        )
        if not session or session.revoked_at or session.expires_at <= datetime.utcnow():
            raise AuthError("Invalid refresh token")
        user = self.db.get(UserDB, session.user_id)
        if not user or not user.is_active:
            raise AuthError("Invalid refresh token")
        session.revoked_at = datetime.utcnow()
        access_token, refresh_token = self._create_session(user, user_agent, ip_address)
        self.db.commit()
        self.db.refresh(user)
        return user, access_token, refresh_token

    def logout(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token:
            session = self.db.scalar(
                select(RefreshTokenSessionDB).where(RefreshTokenSessionDB.token_hash == hash_token(raw_refresh_token))
            )
            if session and not session.revoked_at:
                session.revoked_at = datetime.utcnow()
                self.db.commit()

    def update_profile(self, user: UserDB, request: UpdateProfileRequest) -> UserDB:
        user.display_name = request.displayName
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: UserDB, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("Invalid current password")
        password_error = validate_password_strength(new_password, user.email)
        if password_error:
            raise AuthError(password_error)
        user.password_hash = hash_password(new_password)
        for session in user.refresh_sessions:
            if not session.revoked_at:
                session.revoked_at = datetime.utcnow()
        self.db.commit()

    def forgot_password(self, email: str) -> None:
        user = self.db.scalar(select(UserDB).where(UserDB.email == email.strip().lower()))
        if not user:
            return
        raw, token_hash, expires_at = create_reset_token()
        self.db.add(
            PasswordResetTokenDB(
                id=new_uuid(),
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        self.db.commit()
        reset_link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw}"
        provider = build_email_provider()
        provider.send_email(
            user.email,
            f"{settings.app_name} password reset",
            f"<p>Reset your password: {reset_link}</p>",
            f"Reset your password: {reset_link}",
        )

    def reset_password(self, raw_token: str, new_password: str) -> None:
        token_hash = hash_token(raw_token)
        token = self.db.scalar(select(PasswordResetTokenDB).where(PasswordResetTokenDB.token_hash == token_hash))
        if not token or token.used_at or token.expires_at <= datetime.utcnow():
            raise AuthError("Invalid or expired reset token")
        user = self.db.get(UserDB, token.user_id)
        if not user:
            raise AuthError("Invalid or expired reset token")
        password_error = validate_password_strength(new_password, user.email)
        if password_error:
            raise AuthError(password_error)
        user.password_hash = hash_password(new_password)
        token.used_at = datetime.utcnow()
        for session in user.refresh_sessions:
            if not session.revoked_at:
                session.revoked_at = datetime.utcnow()
        self.db.commit()

    def _create_session(self, user: UserDB, user_agent: str | None, ip_address: str | None) -> tuple[str, str]:
        access_token = create_access_token(user.id)
        refresh_token, token_hash, expires_at = create_refresh_token()
        self.db.add(
            RefreshTokenSessionDB(
                id=new_uuid(),
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        return access_token, refresh_token


def auth_user_response(user: UserDB) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        displayName=user.display_name,
        isVerified=user.is_verified,
        createdAt=user.created_at,
    )
