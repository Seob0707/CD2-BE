from fastapi import APIRouter, Depends, HTTPException
from api.database import get_db
from api.domain.ai_service import call_ai
from jose import JWTError
import httpx

router = APIRouter(tags=["AI"])


@router.post("/{model_name}")
async def proxy_to_ai(model_name: str, body: dict):
    try:
        result = await call_ai(f"/{model_name}", body)
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
