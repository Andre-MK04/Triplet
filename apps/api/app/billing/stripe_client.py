import stripe
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import UserDB


class BillingConfigError(ValueError):
    pass


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
        metadata={"user_id": user.id, "app": "Triplet"},
    )
    user.stripe_customer_id = customer["id"]
    db.commit()
    db.refresh(user)
    return user.stripe_customer_id


def create_checkout_session(db: Session, user: UserDB, interval: str):
    require_billing_enabled()
    if interval not in {"monthly", "yearly"}:
        raise BillingConfigError("Invalid billing interval.")
    price_attr = "stripe_price_pro_monthly" if interval == "monthly" else "stripe_price_pro_yearly"
    require_stripe_config("stripe_secret_key", price_attr)
    customer_id = create_or_get_customer(db, user)
    price_id = getattr(settings, price_attr)
    return stripe_api().checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        metadata={"user_id": user.id, "app": "Triplet", "plan": "pro"},
        subscription_data={"metadata": {"user_id": user.id, "app": "Triplet", "plan": "pro"}},
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
