import hashlib
import logging
import time
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
import jwt
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.auth.native_identity import token_cipher
from app.config import settings
from app.database import SessionLocal
from app.db.models import PushDeviceDB, PushDeliveryDB, SavedSearchDB

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
_jwt_cache: tuple[tuple, float, str] | None = None


def push_configured() -> bool:
    if not (settings.apns_enabled and settings.apns_team_id and settings.apns_key_id
            and settings.apns_private_key and settings.apns_topic
            and settings.apns_environment in {"sandbox", "production"}):
        return False
    try:
        key = serialization.load_pem_private_key(settings.apns_private_key.replace("\\n", "\n").encode(), password=None)
        return isinstance(key, ec.EllipticCurvePrivateKey) and isinstance(key.curve, ec.SECP256R1)
    except (ValueError, TypeError):
        return False


def register_device(db: Session, user_id: str, token: str) -> PushDeviceDB:
    digest = hashlib.sha256(token.lower().encode()).hexdigest()
    row = db.scalar(select(PushDeviceDB).where(PushDeviceDB.token_hash == digest,
        PushDeviceDB.topic == settings.apns_topic, PushDeviceDB.environment == settings.apns_environment).with_for_update())
    if row and row.user_id != user_id:
        if row.is_active:
            raise ValueError("This device must be disconnected from its previous account first.")
        # Explicit revocation by the previous owner permits a new account on
        # this phone. Never reuse that owner's device id or queued deliveries.
        db.execute(delete(PushDeliveryDB).where(PushDeliveryDB.device_id == row.id))
        db.delete(row)
        db.flush()
        row = None
    if not row:
        count = len(db.scalars(select(PushDeviceDB.id).where(PushDeviceDB.user_id == user_id)).all())
        if count >= 8: raise ValueError("This account has reached its registered device limit.")
        row = PushDeviceDB(id=str(uuid4()), user_id=user_id, token_hash=digest,
            encrypted_token=token_cipher().encrypt(token.lower().encode()).decode(),
            topic=settings.apns_topic, environment=settings.apns_environment, is_active=True)
        db.add(row)
    else:
        row.is_active = True
        row.updated_at = datetime.utcnow()
    db.commit()
    return row


def enqueue_watch_push(db: Session, watch: SavedSearchDB, run_id: str) -> int:
    if not watch.user_id or not push_configured(): return 0
    devices = db.scalars(select(PushDeviceDB).where(PushDeviceDB.user_id == watch.user_id,
        PushDeviceDB.is_active.is_(True), PushDeviceDB.topic == settings.apns_topic,
        PushDeviceDB.environment == settings.apns_environment)).all()
    count = 0
    for device in devices:
        existing = db.scalar(select(PushDeliveryDB.id).where(PushDeliveryDB.device_id == device.id,
                                                            PushDeliveryDB.alert_run_id == run_id))
        if existing: continue
        db.add(PushDeliveryDB(id=str(uuid4()), device_id=device.id, saved_search_id=watch.id,
            alert_run_id=run_id, status="pending", attempts=0, next_attempt_at=datetime.utcnow()))
        count += 1
    return count


def _provider_token() -> str:
    global _jwt_cache
    now = time.time()
    fingerprint = (settings.apns_team_id, settings.apns_key_id, hashlib.sha256(settings.apns_private_key.encode()).digest())
    if _jwt_cache and _jwt_cache[0] == fingerprint and now - _jwt_cache[1] < 50 * 60:
        return _jwt_cache[2]
    token = jwt.encode({"iss": settings.apns_team_id, "iat": int(now)},
        settings.apns_private_key.replace("\\n", "\n"), algorithm="ES256", headers={"kid": settings.apns_key_id})
    _jwt_cache = (fingerprint, now, token)
    return token


def send_to_apns(device: PushDeviceDB, delivery: PushDeliveryDB) -> str:
    token = token_cipher().decrypt(device.encrypted_token.encode()).decode()
    host = "https://api.sandbox.push.apple.com" if device.environment == "sandbox" else "https://api.push.apple.com"
    # Generic lock-screen content: no email, route, price or bearer/booking tokens.
    payload = {"aps": {"alert": {"title": "Farelin", "body": "Your watch has new trip ideas. Open Farelin to explore."},
                        "sound": "default", "thread-id": delivery.saved_search_id},
               "watchId": delivery.saved_search_id}
    with httpx.Client(http2=True, timeout=10) as client:
        response = client.post(f"{host}/3/device/{token}", json=payload, headers={
            "authorization": f"bearer {_provider_token()}", "apns-topic": device.topic,
            "apns-push-type": "alert", "apns-priority": "5", "apns-id": delivery.id,
            "apns-expiration": str(int(time.time()) + 3600), "apns-collapse-id": delivery.saved_search_id,
        })
    if response.status_code == 200: return "sent"
    reason = response.json().get("reason", "") if response.content else ""
    if response.status_code == 410 or reason in {"BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"}: return "invalid_device"
    if response.status_code == 429 or response.status_code >= 500: return "retry"
    return "failed"


def deliver_pending_push(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    summary = {"sent": 0, "failed": 0, "retried": 0, "enabled": push_configured()}
    if not summary["enabled"]: return summary
    rows = db.scalars(select(PushDeliveryDB).where(PushDeliveryDB.status.in_(["pending", "sending"]),
        PushDeliveryDB.next_attempt_at <= now, PushDeliveryDB.attempts < MAX_ATTEMPTS)
        .order_by(PushDeliveryDB.next_attempt_at).limit(100)).all()
    for row in rows:
        claim = db.execute(update(PushDeliveryDB).where(PushDeliveryDB.id == row.id,
            PushDeliveryDB.status.in_(["pending", "sending"]), PushDeliveryDB.next_attempt_at <= now,
            PushDeliveryDB.attempts < MAX_ATTEMPTS).values(status="sending", attempts=PushDeliveryDB.attempts + 1,
                                                        next_attempt_at=now + timedelta(minutes=5)))
        db.commit()
        if claim.rowcount != 1: continue
        db.refresh(row)
        device = db.get(PushDeviceDB, row.device_id)
        watch = db.get(SavedSearchDB, row.saved_search_id)
        if not device or not device.is_active or not watch or not watch.is_active or device.user_id != watch.user_id:
            result = "failed"
        elif device.topic != settings.apns_topic or device.environment != settings.apns_environment:
            result = "failed"
        elif row.created_at < now - timedelta(days=1):
            result = "failed"  # Never push an old opportunity after a long outage.
        else:
            try: result = send_to_apns(device, row)
            except (httpx.HTTPError, InvalidToken, ValueError): result = "retry"
        if result == "sent":
            row.status = "sent"; row.sent_at = now; summary["sent"] += 1
        elif result == "retry" and row.attempts < MAX_ATTEMPTS:
            row.status = "pending"; row.next_attempt_at = now + timedelta(minutes=15 * row.attempts)
            summary["retried"] += 1
        else:
            row.status = "failed"; summary["failed"] += 1
            if result == "invalid_device" and device: device.is_active = False
        db.commit()
    # A worker killed on its last attempt must not leave an eternal sending row.
    db.execute(update(PushDeliveryDB).where(PushDeliveryDB.status == "sending",
        PushDeliveryDB.next_attempt_at <= now, PushDeliveryDB.attempts >= MAX_ATTEMPTS).values(status="failed"))
    db.commit()
    return summary


def run_push_delivery() -> dict:
    with SessionLocal() as db: return deliver_pending_push(db)
