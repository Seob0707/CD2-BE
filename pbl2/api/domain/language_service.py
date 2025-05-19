from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select 
                                    
from typing import List

from api.models.ORM import Language 

async def get_all_languages(db: AsyncSession) -> List[Language]:
    stmt = select(Language).order_by(Language.lang_id)
    result = await db.execute(stmt)
    languages = result.scalars().all()
    return languages