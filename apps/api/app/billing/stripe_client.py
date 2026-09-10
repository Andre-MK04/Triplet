import stripe
from sqlalchemy.orm import Session

from app.billing.entitlements import get_user_plan
from app.config import settings
from app.db.models import UserDB


class BillingConfigError(ValueError):
    pass


class BillingStateError(ValueError):
    """The Stripe configuration works, but this account may not start Checkout."""


def require_billing_enabled() -> None:
    if not settings.billing_enabled:
        raise BillingConfigError("Billing is not enabled in this environment.")
    if settings.billing_provider != "stripe":
        raise BillingConfigError("Stripe is the only supported billing provider.")


def require_stripe_config(*names: str) -> None:
    missing = [name for name in names if not getattr(settings, name)]
    if missing:
        raise BillingConfigError(f"Missing Stripe billing configuration: {', '.join(missing)}.")


def stripe_api():
    require_billing_enabled()
    require_stripe_config("stripe_secret_key")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_or_get_customer(db: Session, user: UserDB) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    require_stripe_config("stripe_secret_key")
    customer = stripe_api().Customer.create(
        email=user.email,
        name=user.display_name,
        metadata={"user_id": user.id, "app": settings.app_name},
        # If Stripe accepted the customer but our database commit was retried,
        # the same user still gets the same Customer instead of a duplicate.
        idempotency_key=f"farelin-customer-{user.id}",
    )
    user.stripe_customer_id = customer["id"]
    db.commit()
    db.refresh(user)
    return user.stripe_customer_id


def create_checkout_session(db: Session, user: UserDB, interval: str):
    require_billing_enabled()
    if not user.is_verified:
        raise BillingStateError("Verify your email before starting a paid subscription.")
    if get_user_plan(user) in {"pro", "owner"}:
        raise BillingStateError("Farelin Pro is already active. Use Manage billing instead.")
    if interval not in {"monthly", "yearly"}:
        raise BillingConfigError("Invalid billing interval.")
    price_attr = "stripe_price_pro_monthly" if interval == "monthly" else "stripe_price_pro_yearly"
    require_stripe_config("stripe_secret_key", price_attr)
    customer_id = create_or_get_customer(db, user)
    price_id = getattr(settings, price_attr)
    return stripe_api().checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=user.id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        billing_address_collection="auto",
        automatic_tax={"enabled": settings.stripe_automatic_tax_enabled},
        **(
            {
                "customer_update": {"address": "auto", "name": "auto"},
                "tax_id_collection": {"enabled": True},
            }
            if settings.stripe_automatic_tax_enabled
            else {}
        ),
        metadata={"user_id": user.id, "app": settings.app_name, "plan": "pro"},
        subscription_data={"metadata": {"user_id": user.id, "app": settings.app_name, "plan": "pro"}},
    )


def create_billing_portal_session(user: UserDB):
    require_billing_enabled()
    require_stripe_config("stripe_secret_key")
    if not user.stripe_customer_id:
        raise BillingConfigError("No Stripe customer exists for this user.")
    return stripe_api().billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=settings.billing_portal_return_url,
    )


def verify_webhook_signature(raw_body: bytes, signature_header: str | None):
    require_billing_enabled()
    require_stripe_config("stripe_webhook_secret")
    if not signature_header:
        raise BillingConfigError("Missing Stripe signature.")
    try:
        return stripe.Webhook.construct_event(raw_body, signature_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise BillingConfigError("Invalid Stripe webhook signature.") from exc
