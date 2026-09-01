from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str
    displayName: str | None = Field(default=None, max_length=160)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return normalized


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthUserResponse(BaseModel):
    id: str
    email: str
    displayName: str | None = None
    isVerified: bool
    createdAt: datetime
    #: False for an account created through a provider that has never set a
    #: password. Without this the account page showed a "current password" form
    #: that such a user could never fill in, and no explanation of why.
    hasPassword: bool = True
    #: Providers linked to this account, e.g. ["google"]. Lets the interface say
    #: how someone actually signs in rather than assuming it was email.
    connectedProviders: list[str] = []


class AuthResponse(BaseModel):
    user: AuthUserResponse
    message: str


class UpdateProfileRequest(BaseModel):
    displayName: str | None = Field(default=None, max_length=160)


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    newPassword: str
