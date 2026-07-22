from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PlanInfo(BaseModel):
    plan: str
    name: str
    priceLabel: str
    priceYearlyLabel: str | None = None
    features: list[str]
    limits: dict
    stripeMonthlyPriceId: str | None = None
    stripeYearlyPriceId: str | None = None


class CreateCheckoutSessionRequest(BaseModel):
    interval: Literal["monthly", "yearly"]


class CreateCheckoutSessionResponse(BaseModel):
    checkoutUrl: str


class CreateBillingPortalSessionResponse(BaseModel):
    portalUrl: str


class BillingStatusResponse(BaseModel):
    plan: str
    subscriptionStatus: str
    currentPeriodEnd: datetime | None = None
    cancelAtPeriodEnd: bool = False
    trialEndsAt: datetime | None = None
    trialDaysRemaining: int = 0
    limits: dict
    usage: dict
    canStartTrial: bool = False
    canUpgrade: bool
    canManageBilling: bool


class WebhookResponse(BaseModel):
    received: bool
