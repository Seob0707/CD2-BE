from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.database import get_db
from api.domain import language_service
from api.schemas import language_schema 

router = APIRouter(
    prefix="/languages",
    tags=["languages"]
)

@router.get("/", response_model=List[language_schema.LanguageResponse])
async def read_languages(db: AsyncSession = Depends(get_db)):
    languages = await language_service.get_all_languages(db=db)
    if not languages:
        return []
    return languages