from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.models.ORM import Topic
from api.schemas.topic_schema import TopicOut
from api.core.auth     import get_current_user  

router = APIRouter(
    tags=["Topic"]
)

@router.get(
    "/", 
    response_model=List[TopicOut]
)
async def list_topics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topic))
    return result.scalars().all()
