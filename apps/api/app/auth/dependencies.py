from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.security import ACCESS_COOKIE_NAME, decode_access_token
from app.database import get_db
from app.db.models import UserDB


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> UserDB | None:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    user = db.get(UserDB, user_id)
    if not user or not user.is_active:
        return None
    return user


def get_current_user_required(user: UserDB | None = Depends(get_current_user_optional)) -> UserDB:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
