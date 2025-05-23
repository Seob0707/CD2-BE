from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.models.ORM import User, Setting
from api.core.auth import get_current_user 
from api.domain.language_service import get_effective_lang_code, AUTO_SELECT_LANGUAGE_ID

async def get_resolved_lang_code(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> str:
    setting_result = await db.execute(
        select(Setting).where(Setting.user_id == current_user.user_id)
    )
    user_setting = setting_result.scalars().first()

    user_language_id_pref = AUTO_SELECT_LANGUAGE_ID
    if user_setting and user_setting.language is not None:
        user_language_id_pref = user_setting.language

    lang_code = await get_effective_lang_code(request, user_language_id_pref, db)
    return lang_code