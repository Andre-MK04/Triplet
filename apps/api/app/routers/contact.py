"""Public contact delivery without turning Farelin into a mail relay.

Messages go straight to the configured support inbox and are not persisted in
the application database. The subject is selected from a fixed allowlist,
headers never contain untrusted text, and the endpoint has its own tight rate
limit. We intentionally send no automatic acknowledgement: doing so would let
an anonymous caller make Farelin email arbitrary recipients.
"""

from __future__ import annotations

import html
import logging
from email.utils import parseaddr
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.alerts.email import EmailProviderError, build_email_provider, contact_recipient
from app.security import RateLimitCategory, check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contact", tags=["contact"])

ContactTopic = Literal["general", "account", "fare", "privacy", "security", "partnership"]

TOPIC_LABELS: dict[str, str] = {
    "general": "General question",
    "account": "Account help",
    "fare": "Fare or trip issue",
    "privacy": "Privacy request",
    "security": "Security report",
    "partnership": "Partnership",
}


class ContactRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    topic: ContactTopic
    message: str = Field(min_length=20, max_length=4000)
    # Hidden form field. A human never fills it; bots commonly do. Returning the
    # same response gives them no signal about the filter and sends no email.
    website: str = Field(default="", max_length=200)

    @field_validator("name", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if any(ch in value for ch in "\r\n"):
            raise ValueError("Enter a valid email address.")
        _, address = parseaddr(value)
        local, separator, domain = address.partition("@")
        if value != address or not local or separator != "@" or not domain or "." not in domain:
            raise ValueError("Enter a valid email address.")
        return value


class ContactResponse(BaseModel):
    accepted: bool


@router.post("", response_model=ContactResponse)
def submit_contact(payload: ContactRequest, request: Request) -> ContactResponse:
    check_rate_limit(RateLimitCategory.CONTACT, request)

    if payload.website:
        return ContactResponse(accepted=True)

    provider = build_email_provider()
    recipient = contact_recipient()
    if not provider.delivers or not recipient:
        logger.warning(
            "contact_delivery_unavailable",
            extra={"event": "contact.delivery", "outcome": "unavailable"},
        )
        raise HTTPException(
            status_code=503,
            detail="Contact email is temporarily unavailable. Please try again later.",
        )

    topic = TOPIC_LABELS[payload.topic]
    escaped_name = html.escape(payload.name)
    escaped_email = html.escape(payload.email)
    escaped_message = html.escape(payload.message).replace("\n", "<br>")
    subject = f"Farelin contact · {topic}"
    text_body = (
        f"New Farelin contact message\n\n"
        f"Topic: {topic}\nName: {payload.name}\nEmail: {payload.email}\n\n"
        f"Message:\n{payload.message}\n"
    )
    html_body = (
        "<h1>New Farelin contact message</h1>"
        f"<p><strong>Topic:</strong> {html.escape(topic)}<br>"
        f"<strong>Name:</strong> {escaped_name}<br>"
        f"<strong>Email:</strong> {escaped_email}</p>"
        f"<p><strong>Message</strong><br>{escaped_message}</p>"
    )

    try:
        provider.send_email(recipient, subject, html_body, text_body, reply_to=payload.email)
    except (EmailProviderError, OSError) as exc:
        logger.warning(
            "contact_delivery_failed",
            extra={
                "event": "contact.delivery",
                "outcome": "error",
                "errorType": type(exc).__name__,
                "topic": payload.topic,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="We could not send your message. Please try again in a moment.",
        ) from exc

    logger.info(
        "contact_delivery_accepted",
        extra={"event": "contact.delivery", "outcome": "accepted", "topic": payload.topic},
    )
    return ContactResponse(accepted=True)
