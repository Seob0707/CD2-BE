from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.core.security import admin_required
from api.schemas.admin_schemas import (
    TopicCreate, TopicResponse,
    LanguageCreate, LanguageResponse,
    StatsResponse
)
from api.domain.admin_service import (
    create_topic, delete_topic,
    create_language, delete_language,
    get_visit_stats
)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(admin_required)]
)

@router.post(
    "/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_topic(
    p: TopicCreate,
    db: AsyncSession = Depends(get_db)
):
    return await create_topic(db, p.topic_name)

@router.delete(
    "/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db)
):
    await delete_topic(db, topic_id)

@router.post(
    "/languages",
    response_model=LanguageResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_language(
    p: LanguageCreate,
    db: AsyncSession = Depends(get_db)
):
    return await create_language(db, p.lang_code)

@router.delete(
    "/languages/{language_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def remove_language(
    language_id: int,
    db: AsyncSession = Depends(get_db)
):
    await delete_language(db, language_id)

@router.get(
    "/stats/visits",
    response_model=StatsResponse
)
async def visits_stats(
    db: AsyncSession = Depends(get_db)
):
    stats = await get_visit_stats(db)
    return {"stats": stats}
