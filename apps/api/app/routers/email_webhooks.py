from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.email_delivery import process_resend_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/resend")
async def resend_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    processed = await process_resend_webhook(request, db)
    return {"received": True, "processed": processed}
