from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth.dependencies import get_current_user_required
from app.auth.oauth import (
    OAUTH_STATE_COOKIE_NAME,
    OAuthConfigError,
    OAuthProviderError,
    authorization_url,
    exchange_code_for_profile,
    generate_oauth_state,
    validate_provider,
    verify_oauth_state,
)
from app.auth.rate_limit import auth_rate_limit
from app.auth.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateProfileRequest,
)
from app.auth.security import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.auth.service import AuthError, AuthService, DuplicateEmailError, auth_user_response
from app.config import settings
from app.database import get_db
from app.db.models import UserDB

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(
    request_data: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit("signup")),
) -> AuthResponse:
    try:
        user, access_token, refresh_token = AuthService(db).signup(
            request_data,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
    record_audit_event(db, "auth.signup", user_id=user.id, request=request, commit=True)
    set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(user=auth_user_response(user), message="Signed up.")


@router.post("/login", response_model=AuthResponse)
def login(
    request_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit("login")),
) -> AuthResponse:
    try:
        user, access_token, refresh_token = AuthService(db).login(
            request_data.email,
            request_data.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthError as exc:
        record_audit_event(db, "auth.login_failed", request=request, commit=True)
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc
    record_audit_event(db, "auth.login", user_id=user.id, request=request, commit=True)
    set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(user=auth_user_response(user), message="Logged in.")


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, response: Response, _: None = Depends(auth_rate_limit("oauth_start"))):
    try:
        normalized_provider = validate_provider(provider)
        state = generate_oauth_state()
        response = RedirectResponse(authorization_url(normalized_provider, state), status_code=302)
        response.set_cookie(
            OAUTH_STATE_COOKIE_NAME,
            state,
            max_age=10 * 60,
            **cookie_settings(),
        )
        return response
    except OAuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/oauth/{provider}/callback")
@router.post("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit("oauth_callback")),
):
    try:
        normalized_provider = validate_provider(provider)
        code, state = await _oauth_callback_params(request)
        if not code or not verify_oauth_state(state, request.cookies.get(OAUTH_STATE_COOKIE_NAME)):
            raise OAuthProviderError("OAuth state could not be verified.")
        profile = await exchange_code_for_profile(normalized_provider, code)
        user, access_token, refresh_token = AuthService(db).login_with_oauth(
            profile,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except (OAuthConfigError, OAuthProviderError, AuthError):
        response = RedirectResponse(f"{settings.frontend_url.rstrip('/')}?auth=oauth_failed", status_code=302)
        response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path="/", domain=cookie_settings().get("domain"))
        return response
    except SQLAlchemyError:
        db.rollback()
        response = RedirectResponse(f"{settings.frontend_url.rstrip('/')}?auth=database_unavailable", status_code=302)
        response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path="/", domain=cookie_settings().get("domain"))
        return response

    record_audit_event(db, "auth.oauth_login", user_id=user.id, request=request, commit=True, provider=normalized_provider)
    response = RedirectResponse(f"{settings.frontend_url.rstrip('/')}?auth=oauth_success", status_code=302)
    set_auth_cookies(response, access_token, refresh_token)
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path="/", domain=cookie_settings().get("domain"))
    return response


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, bool]:
    AuthService(db).logout(request.cookies.get(REFRESH_COOKIE_NAME))
    record_audit_event(db, "auth.logout", request=request, commit=True)
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        user, access_token, refresh_token = AuthService(db).refresh(
            raw_refresh,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthError as exc:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Authentication required.") from exc
    set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(user=auth_user_response(user), message="Refreshed.")


@router.get("/me", response_model=AuthResponse)
def me(user: UserDB = Depends(get_current_user_required)) -> AuthResponse:
    return AuthResponse(user=auth_user_response(user), message="Authenticated.")


@router.patch("/me", response_model=AuthResponse)
def update_me(
    request_data: UpdateProfileRequest,
    user: UserDB = Depends(get_current_user_required),
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = AuthService(db).update_profile(user, request_data)
    return AuthResponse(user=auth_user_response(user), message="Profile updated.")


@router.post("/change-password")
def change_password(
    request_data: ChangePasswordRequest,
    user: UserDB = Depends(get_current_user_required),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        AuthService(db).change_password(user, request_data.currentPassword, request_data.newPassword)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(db, "auth.password_changed", user_id=user.id, commit=True)
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(
    request_data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit("forgot_password")),
) -> dict[str, str]:
    AuthService(db).forgot_password(request_data.email)
    record_audit_event(db, "auth.password_reset_requested", commit=True)
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(
    request_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit("reset_password")),
) -> dict[str, bool]:
    try:
        AuthService(db).reset_password(request_data.token, request_data.newPassword)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(db, "auth.password_reset_completed", commit=True)
    return {"ok": True}


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    cookie_args = cookie_settings()
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=settings.auth_access_token_expire_minutes * 60,
        **cookie_args,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.auth_refresh_token_expire_days * 24 * 60 * 60,
        **cookie_args,
    )


def clear_auth_cookies(response: Response) -> None:
    cookie_args = cookie_settings()
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", domain=cookie_args.get("domain"))
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/", domain=cookie_args.get("domain"))


def cookie_settings() -> dict:
    args = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
    }
    if settings.auth_cookie_domain:
        args["domain"] = settings.auth_cookie_domain
    return args


async def _oauth_callback_params(request: Request) -> tuple[str | None, str | None]:
    if request.method == "POST":
        body = (await request.body()).decode()
        parsed = parse_qs(body)
        return _first(parsed.get("code")), _first(parsed.get("state"))
    return request.query_params.get("code"), request.query_params.get("state")


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]
