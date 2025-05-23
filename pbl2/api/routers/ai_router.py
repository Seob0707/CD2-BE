from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import ai_service 
from api.core.auth import get_current_user 
from api.models.ORM import User 
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Features"])

@router.post("/{model_name}")
async def proxy_to_ai(model_name: str, body: dict):
    try:
        result = await ai_service.call_ai(f"/{model_name}", body)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
