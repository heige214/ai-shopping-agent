from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest, UserOut
from app.modules.auth import service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> User:
    """注册接口：创建账号并返回用户公开信息。"""
    return await service.register_user(db, data)
