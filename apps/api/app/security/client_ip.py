"""Canonical, deployment-aware client IP resolution.

Railway documents ``X-Real-IP`` as the edge-generated remote address. We never
read X-Forwarded-For: its left-most value may be supplied by the caller, which
would let an anonymous user rotate their rate-limit identity.
"""

from __future__ import annotations

from ipaddress import ip_address

from app.config import settings


def client_ip(request) -> str | None:
    """Return a validated trusted-edge IP, or the direct socket peer."""

    if settings.trust_proxy_headers:
        candidate = request.headers.get(settings.trusted_client_ip_header, "").strip()
        try:
            return str(ip_address(candidate)) if candidate else _peer_ip(request)
        except ValueError:
            return _peer_ip(request)
    return _peer_ip(request)


def _peer_ip(request) -> str | None:
    client = getattr(request, "client", None)
    return client.host if client and client.host else None
