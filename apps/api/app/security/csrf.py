"""Cross-site request forgery protection for cookie-authenticated requests.

Triplet authenticates with cookies, which browsers attach to any request a
third-party page provokes. Origin checking alone was the only defence, and it
has a gap by construction: the check can only reject an Origin it can see, so a
request that arrives without the header passes it.

The scheme here is signed double-submit. The server issues a random value in a
JavaScript-readable cookie and the client echoes it in a header. An attacker on
another origin can cause the cookie to be *sent* but cannot read it to build the
matching header, because the same-origin policy stops them.

Signed rather than plain double-submit: a plain one trusts whatever is in the
cookie, so an attacker able to write cookies for a sibling subdomain could plant
a value and echo it themselves. The token carries an HMAC over the app secret,
so a token Triplet did not issue is rejected however consistently it is
presented.

Only cookie-authenticated requests are covered. A request carrying no session
cookie has no session to forge, and a Bearer token has to be deliberately
attached by a caller rather than volunteered by the browser — neither is
reachable through CSRF, and demanding a token from them would break API clients
and webhooks for no security gain.
"""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from app.config import settings
from app.auth.security import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME

CSRF_COOKIE_NAME = "triplet_csrf"
CSRF_HEADER_NAME = "x-csrf-token"

#: Methods that can change state. GET/HEAD/OPTIONS are exempt by definition.
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Paths that authenticate by a means the browser cannot be tricked into
#: supplying, and so cannot be targets of CSRF.
EXEMPT_PREFIXES: tuple[str, ...] = (
    # OAuth providers redirect the browser back here; there is no token to carry
    # across the hop, and the flow has its own state parameter.
    "/auth/oauth/",
    # Stripe signs its webhooks. Requiring a browser token here would simply
    # break them, and the signature is the stronger check.
    "/billing/webhook",
)


def _sign(raw: str) -> str:
    return hmac.new(settings.app_secret.encode(), raw.encode(), sha256).hexdigest()


def issue_token() -> str:
    """Mint a token: a random value plus an HMAC binding it to this deployment."""
    raw = secrets.token_urlsafe(32)
    return f"{raw}.{_sign(raw)}"


def token_is_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    raw, _, signature = token.rpartition(".")
    if not raw or not signature:
        return False
    return hmac.compare_digest(_sign(raw), signature)


def is_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def request_uses_cookie_auth(request) -> bool:
    """Whether this request relies on cookies the browser attached by itself."""
    return bool(
        request.cookies.get(ACCESS_COOKIE_NAME) or request.cookies.get(REFRESH_COOKIE_NAME)
    )


def check(request) -> str | None:
    """Return a rejection reason, or None when the request may proceed."""
    if request.method not in UNSAFE_METHODS:
        return None
    if is_exempt(request.url.path):
        return None
    if not request_uses_cookie_auth(request):
        # Nothing for an attacker to ride: no ambient credential is in play.
        return None

    header_token = request.headers.get(CSRF_HEADER_NAME)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not header_token or not cookie_token:
        return "Missing CSRF token."
    if not hmac.compare_digest(header_token, cookie_token):
        return "CSRF token mismatch."
    if not token_is_valid(header_token):
        # Presented consistently, but not a token this deployment ever issued.
        return "Invalid CSRF token."
    return None


def set_cookie(response, token: str) -> None:
    """Attach the token cookie.

    Deliberately NOT HttpOnly: the frontend has to read it to build the header,
    which is the entire mechanism. It is not a credential on its own — it grants
    nothing without the session cookie that sits beside it.
    """
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        max_age=60 * 60 * 12,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite.lower(),
        path="/",
    )
