"""Best-effort audit trail for sensitive actions.

Audit entries never contain secrets, tokens, or passwords — only the action name,
the acting user id, a hashed client IP, and small structured metadata. Recording
failures are logged and swallowed: auditing must never break the audited action.
"""

import hashlib
import logging
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEventDB

logger = logging.getLogger(__name__)

# Keys that must never end up in audit metadata, even by accident.
FORBIDDEN_METADATA_KEYS = {"password", "token", "secret", "authorization", "cookie", "key"}


def record_audit_event(
    db: Session,
    action: str,
    user_id: str | None = None,
    request: Request | None = None,
    commit: bool = False,
    **metadata: Any,
) -> None:
    try:
        clean_metadata = {
            key: value
            for key, value in metadata.items()
            if value is not None and not any(word in key.lower() for word in FORBIDDEN_METADATA_KEYS)
        }
        db.add(
            AuditEventDB(
                action=action,
                user_id=user_id,
                request_id=request.headers.get("x-request-id") if request else None,
                ip_hash=hash_client_ip(request),
                event_metadata=clean_metadata or None,
            )
        )
        if commit:
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("audit_event_failed action=%s", action)
    except Exception:  # noqa: BLE001 - auditing must never break the audited action.
        logger.exception("audit_event_failed action=%s", action)


def hash_client_ip(request: Request | None) -> str | None:
    if not request or not request.client or not request.client.host:
        return None
    return hashlib.sha256(f"{settings.app_secret}:{request.client.host}".encode()).hexdigest()[:32]
