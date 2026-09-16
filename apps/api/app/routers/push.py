from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_required
from app.config import settings
from app.database import get_db
from app.db.models import PushDeviceDB, UserDB
from app.notifications.service import push_configured, register_device
from app.security import RateLimitCategory, check_rate_limit

router = APIRouter(prefix="/me/push", tags=["native notifications"])


class RegisterDevice(BaseModel):
    token: str = Field(pattern=r"^(?:[a-fA-F0-9]{2}){32,100}$")
    topic: str = Field(min_length=3, max_length=255)
    environment: str = Field(pattern=r"^(sandbox|production)$")


@router.get("/status")
def push_status(user: UserDB = Depends(get_current_user_required), db: Session = Depends(get_db)):
    devices = db.scalars(select(PushDeviceDB).where(PushDeviceDB.user_id == user.id)).all()
    return {"enabled": push_configured(), "topic": settings.apns_topic, "environment": settings.apns_environment,
            "devices": [{"id": d.id, "isActive": d.is_active} for d in devices]}


@router.post("/devices")
def add_device(payload: RegisterDevice, request: Request, user: UserDB = Depends(get_current_user_required),
               db: Session = Depends(get_db)):
    check_rate_limit(RateLimitCategory.CHEAP, request)
    if not user.is_verified: raise HTTPException(status_code=403, detail="Confirm your email before enabling notifications.")
    if not push_configured(): raise HTTPException(status_code=503, detail="Push notifications are not configured yet.")
    if payload.topic != settings.apns_topic or payload.environment != settings.apns_environment:
        raise HTTPException(status_code=400, detail="This build is not configured for this push environment.")
    try:
        device = register_device(db, user.id, payload.token)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This device could not be registered for this account.") from exc
    return {"id": device.id, "isActive": device.is_active}


@router.delete("/devices/{device_id}")
def disconnect_device(device_id: str, user: UserDB = Depends(get_current_user_required), db: Session = Depends(get_db)):
    row = db.scalar(select(PushDeviceDB).where(PushDeviceDB.id == device_id, PushDeviceDB.user_id == user.id))
    if not row: raise HTTPException(status_code=404, detail="Device not found.")
    row.is_active = False
    db.commit()
    return {"ok": True}
