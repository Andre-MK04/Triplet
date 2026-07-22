from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth.dependencies import get_current_user_required
from app.billing.schemas import (
    BillingStatusResponse,
    CreateBillingPortalSessionResponse,
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    PlanInfo,
    WebhookResponse,
)
from app.billing.service import TrialError, available_plans, billing_status, start_trial
from app.billing.stripe_client import (
    BillingConfigError,
    create_billing_portal_session,
    create_checkout_session,
    verify_webhook_signature,
)
from app.billing.webhooks import process_stripe_event
from app.database import get_db
from app.db.models import UserDB

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanInfo])
def get_plans() -> list[PlanInfo]:
    return available_plans()


@router.get("/status", response_model=BillingStatusResponse)
def get_billing_status(
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> BillingStatusResponse:
    return BillingStatusResponse(**billing_status(db, user))


@router.post("/start-trial", response_model=BillingStatusResponse)
def start_pro_trial(
    request: Request,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> BillingStatusResponse:
    try:
        status = start_trial(db, user)
    except TrialError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
    record_audit_event(db, "billing.trial_started", user_id=user.id, request=request, commit=True)
    return BillingStatusResponse(**status)


@router.post("/create-checkout-session", response_model=CreateCheckoutSessionResponse)
def create_checkout(
    request_data: CreateCheckoutSessionRequest,
    db: Session = Depends(get_db),
    user: UserDB = Depends(get_current_user_required),
) -> CreateCheckoutSessionResponse:
    try:
        session = create_checkout_session(db, user, request_data.interval)
        return CreateCheckoutSessionResponse(checkoutUrl=session["url"])
    except BillingConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc


@router.post("/create-portal-session", response_model=CreateBillingPortalSessionResponse)
def create_portal(
    user: UserDB = Depends(get_current_user_required),
) -> CreateBillingPortalSessionResponse:
    try:
        session = create_billing_portal_session(user)
        return CreateBillingPortalSessionResponse(portalUrl=session["url"])
    except BillingConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> WebhookResponse:
    raw_body = await request.body()
    try:
        event = verify_webhook_signature(raw_body, stripe_signature)
        process_stripe_event(db, dict(event))
    except BillingConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WebhookResponse(received=True)
