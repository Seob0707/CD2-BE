from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.models.ORM import User, Setting
from api.core.auth import get_current_user

from pydantic import BaseModel, Field

class SettingBase(BaseModel):
    thema: bool = Field(default=True, description="테마 설정 (True: 활성, False: 비활성)")
    memory: bool = Field(default=True, description="메모리 최적화 사용 여부")
    language: int = Field(default=1, description="언어 설정 ID ")

class SettingUpdate(BaseModel):
    thema: bool | None = None
    memory: bool | None = None
    language: int | None = None

class SettingResponse(SettingBase):
    user_id: int
    setting_id: int

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["User Settings"],
    responses={
        401: {"description": "인증 실패"},
        403: {"description": "권한 없음"},
    }
)

@router.get("/", response_model=SettingResponse)
async def read_user_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Setting).where(Setting.user_id == current_user.user_id)
    )
    user_settings = result.scalars().first()

    if not user_settings:
        user_settings = Setting(user_id=current_user.user_id)
        db.add(user_settings)
        await db.commit()
        await db.refresh(user_settings)
        
    return user_settings

@router.put("/", response_model=SettingResponse)
async def update_or_create_user_settings(
    settings_payload: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Setting).where(Setting.user_id == current_user.user_id)
    )
    db_settings = result.scalars().first()

    if not db_settings:
        db_settings = Setting(user_id=current_user.user_id)
        
        if settings_payload.thema is not None:
            db_settings.thema = settings_payload.thema
        if settings_payload.memory is not None:
            db_settings.memory = settings_payload.memory
        if settings_payload.language is not None:
            db_settings.language = settings_payload.language
        
        db.add(db_settings)
    else:
        update_data = settings_payload.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            if value is not None:
                 setattr(db_settings, key, value)

    await db.commit()
    await db.refresh(db_settings)
    return db_settings