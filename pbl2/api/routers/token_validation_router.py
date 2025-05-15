from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.token_schema import TokenPayload, TokenValidationResponse
from api.core.security import decode_token
from api.domain.user_service import get_user_by_id
from api.database import get_db

router = APIRouter()

@router.post(
    "/validate-token",
    response_model=TokenValidationResponse,
    summary="액세스 토큰 유효성 검증",
    description="AI서버에서 프론트엔드로부터 전달받은 JWS 액세스 토큰의 유효성을 검증합니다."
)
async def validate_access_token_for_internal_service(
    payload: TokenPayload = Body(...),
    db: AsyncSession = Depends(get_db)
):
    token_data = decode_token(payload.token)

    if not token_data:
        return TokenValidationResponse(is_valid=False, message="토큰이 유효하지 않거나 만료되었습니다. (디코딩 실패)")

    user_id_from_token_str = token_data.get("sub")
    server_env_from_token = token_data.get("server_env")

    if not user_id_from_token_str:
        return TokenValidationResponse(is_valid=False, message="토큰에 사용자 식별자(sub)가 포함되어 있지 않습니다.")

    try:
        user_id = int(user_id_from_token_str)
    except ValueError:
        return TokenValidationResponse(is_valid=False, message="토큰의 사용자 식별자(sub) 형식이 올바르지 않습니다.")

    user = await get_user_by_id(db, user_id=user_id)

    if not user:
        return TokenValidationResponse(
            is_valid=False,
            message=f"토큰에 해당하는 사용자(ID: {user_id})를 찾을 수 없습니다."
        )

    return TokenValidationResponse(
        is_valid=True,
        user_id=str(user.user_id),
        email=user.email,
        role=user.role,
        message=f"토큰이 유효합니다. (발급 환경: {server_env_from_token or '알 수 없음'})"
    )