"""认证相关路由."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.dto import LoginRequest, TokenResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenResponse(access_token=create_access_token(user.username))
