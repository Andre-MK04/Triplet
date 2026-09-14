from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str
    displayName: str | None = Field(default=None, max_length=160)
    #: Which published versions the signup form showed. Optional in the schema
    #: and checked in the service, so an older client gets a clear message
    #: rather than a validation error it cannot interpret. The value is never
    #: trusted as given — it is compared against the current version, so a
    #: client cannot record acceptance of something that was never published.
    acceptedTermsVersion: str | None = Field(default=None, max_length=32)
    acknowledgedPrivacyVersion: str | None = Field(default=None, max_length=32)

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


class NativeAuthResponse(BaseModel):
    """Credentials returned only by the native-client auth endpoints.

    Browser routes deliberately continue returning cookies. Keeping this as a
    separate response type makes it difficult to expose bearer credentials by
    accidentally changing the established web contract.
    """

    user: AuthUserResponse
    accessToken: str
    refreshToken: str
    tokenType: Literal["Bearer"] = "Bearer"
    expiresInSeconds: int


class NativeRefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=32, max_length=512)


class NativeLogoutRequest(BaseModel):
    refreshToken: str = Field(min_length=32, max_length=512)


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


class VerifyEmailRequest(BaseModel):
    """The token from a verification link, and nothing else.

    No email field: the token identifies the account, so accepting an address
    here would only create a way to guess at one.
    """

    token: str = Field(min_length=16, max_length=512)


class NativeVerifyEmailCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
