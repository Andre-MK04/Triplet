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


class PlansResponse(BaseModel):
    """Everything the pricing page needs, so it invents none of it.

    The plans used to be described twice — configured limits on one side, and
    hand-written feature strings and a comparison table on the other. Both
    happened to agree, which is the dangerous kind of duplication: changing a
    limit silently made the pricing page wrong rather than breaking anything.
    """

    plans: list[PlanInfo]
    #: Whether checkout can actually complete. False means Stripe is not
    #: configured, and the interface must not offer a flow that ends in an error.
    billingEnabled: bool
    #: How many origin airports a signed-out visitor may search with.
    #:
    #: Not a plan, so it is not in `plans` — but the origin picker has to know
    #: it, because searching with more than this is refused with a 402 rather
    #: than quietly trimmed. Served here so the interface reads the number from
    #: configuration instead of repeating it.
    anonymousMaxOriginAirports: int
    #: Only present when both amounts are configured, so no saving is ever
    #: quoted that was not calculated from the real prices.
    yearlySavingsPercent: int | None = None
    trialDurationDays: int


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
