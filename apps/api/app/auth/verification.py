"""Proving that whoever signed up can actually read the address they gave.

Triplet sends mail — watch confirmations, fare alerts, security notices — and
until an address has been proven, the only thing an account's email field
records is what somebody typed into a form.

That distinction was not being drawn. A watch created by a signed-in user was
treated as owning its email purely because it matched the account, so anyone
could sign up as someone else's address, never confirm it, and start Triplet
mailing a stranger. The account email is now proof of nothing until verified,
and this module is what turns it into proof.

Deliberately not coupled to a SavedSearch: watch verification proves a
*watch's* address, this proves an *account's*, and folding one into the other
would mean deleting a watch could unverify an account.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_email_verification_token, hash_token, new_uuid
from app.config import settings
from app.db.models import EmailVerificationTokenDB, UserDB
from app.alerts.email import build_email_provider

logger = logging.getLogger(__name__)

#: Least time between verification emails to one account.
#:
#: Resending is a mail-sending primitive exposed to anyone holding a session,
#: so it is rate limited at the route as well. This is the second line: it
#: bounds how often *any* caller can make Triplet send to a given address.
RESEND_COOLDOWN_SECONDS = 60


class VerificationError(Exception):
    """The token could not be used. The message is safe to show a user."""


def _issue_token(db: Session, user: UserDB) -> str:
    """Mint a token, retiring any earlier one for this account.

    Superseding matters: someone who requests a second link expects the second
    link to work, and expects the first — which may be sitting in a forwarded
    email or a proxy's link cache — to stop working.
    """
    now = datetime.utcnow()
    for existing in db.scalars(
        select(EmailVerificationTokenDB).where(
            EmailVerificationTokenDB.user_id == user.id,
            EmailVerificationTokenDB.used_at.is_(None),
        )
    ):
        existing.used_at = now

    raw, token_hash, expires_at = create_email_verification_token()
    db.add(
        EmailVerificationTokenDB(
            id=new_uuid(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    return raw


def send_verification_email(db: Session, user: UserDB, *, commit: bool = True) -> bool:
    """Issue a link and mail it. Returns whether the mail was accepted.

    A failure here must not cost someone their account. Signup calls this after
    the user row is committed and ignores the result, so a mail outage produces
    an account that exists, is signed in, and can ask for another link — rather
    than a 500 and no account at all.
    """
    if user.is_verified:
        return False

    raw = _issue_token(db, user)
    if commit:
        db.commit()

    link = f"{settings.frontend_url.rstrip('/')}/verify-email?token={raw}"
    try:
        build_email_provider().send_email(
            user.email,
            f"Confirm your {settings.app_name} email",
            (
                f"<p>Confirm this address so {settings.app_name} can send you fare alerts:</p>"
                f'<p><a href="{link}">Confirm my email</a></p>'
                f"<p>The link works once and expires in 24 hours. "
                f"If you did not create an account, ignore this — nothing will be sent to you again.</p>"
            ),
            (
                f"Confirm this address so {settings.app_name} can send you fare alerts:\n{link}\n\n"
                "The link works once and expires in 24 hours. If you did not create an "
                "account, ignore this — nothing will be sent to you again."
            ),
        )
        return True
    except Exception:  # noqa: BLE001 - never let mail delivery break signup
        # Logged without the address: this runs on a path where the address may
        # belong to someone who never asked to be here.
        logger.warning("verification_email_send_failed", exc_info=True)
        return False


def resend_verification(db: Session, user: UserDB) -> bool:
    """Send another link, unless one was just sent.

    Returns False when throttled or already verified. Callers must not report
    which of those it was to an unauthenticated caller.
    """
    if user.is_verified:
        return False

    latest = db.scalar(
        select(EmailVerificationTokenDB)
        .where(EmailVerificationTokenDB.user_id == user.id)
        .order_by(EmailVerificationTokenDB.created_at.desc())
    )
    if latest and latest.created_at:
        age = datetime.utcnow() - latest.created_at
        if age < timedelta(seconds=RESEND_COOLDOWN_SECONDS):
            return False

    return send_verification_email(db, user)


def verify_email(db: Session, raw_token: str) -> UserDB:
    """Consume a token and mark the account verified.

    Every failure raises the same message. Distinguishing "expired" from
    "already used" from "never existed" would let someone probe which tokens
    have been issued; the page offers a fresh link either way.
    """
    token = db.scalar(
        select(EmailVerificationTokenDB).where(
            EmailVerificationTokenDB.token_hash == hash_token(raw_token)
        )
    )
    now = datetime.utcnow()
    if not token or token.used_at or token.expires_at <= now:
        raise VerificationError("This verification link is no longer valid.")

    user = db.get(UserDB, token.user_id)
    if not user:
        raise VerificationError("This verification link is no longer valid.")

    token.used_at = now
    user.is_verified = True
    db.commit()
    db.refresh(user)
    return user
