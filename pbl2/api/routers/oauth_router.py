from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749.errors import OAuth2Error
from starlette.config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import logging

from api.database import get_db
from api.domain import user_service
from api.schemas.user_schema import UserOAuthCreate
from api.core.security import create_access_token

logger = logging.getLogger(__name__)

config = Config(".env")
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=str, default=None)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=str, default=None)
REDIRECT_URI = config("GOOGLE_REDIRECT_URI", cast=str, default=None)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=60)
FRONTEND_CALLBACK_URL = config("FRONTEND_CALLBACK_URL", cast=str, default=None)

if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REDIRECT_URI, FRONTEND_CALLBACK_URL]):
    logger.error("OAuth 관련 필수 환경변수가 설정되지 않았습니다. (.env 파일 확인)")

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "access_type": "offline",
    },
)

router = APIRouter()

@router.get("/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)

@router.get("/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        token_data = await oauth.google.authorize_access_token(request)
    except OAuth2Error as e:
        logger.error(f"Google OAuth 토큰 교환 실패: {e.error} - {e.description}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google 인증에 실패했습니다. (오류: {e.error})"
        )

    user_info_from_token = token_data.get("userinfo")
    if not user_info_from_token:
        try:
            user_info_from_token = await oauth.google.parse_id_token(request, token_data)
        except Exception as e:
            logger.error(f"ID 토큰 파싱 실패: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="사용자 정보를 가져오는 데 실패했습니다.")

    email = user_info_from_token.get("email")
    sub = user_info_from_token.get("sub")
    nickname = user_info_from_token.get("name") or user_info_from_token.get("given_name") or \
                 (email.split('@')[0] if email else None)

    if not email or not sub:
        logger.error(f"Google OAuth 필수 사용자 정보 누락: email={email}, sub={sub}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="필수 사용자 정보(이메일 또는 사용자 ID)가 누락되었습니다.")

    user = await user_service.get_user_by_email(db, email)
    google_refresh_token = token_data.get("refresh_token")

    if not user:
        user_create_dto = UserOAuthCreate(email=email, nickname=nickname)
        try:
            user = await user_service.create_oauth_user(
                db=db,
                user_data=user_create_dto,
                oauth_provider="google",
                oauth_id=sub,
                refresh_token_val=google_refresh_token
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"OAuth 사용자 생성 중 오류 발생: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="사용자 계정 생성 중 오류가 발생했습니다.")
    else:
        try:
            user = await user_service.update_user_oauth_details(
                db=db,
                user=user,
                nickname=nickname,
                oauth_provider="google",
                oauth_id=sub,
                new_refresh_token=google_refresh_token
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"OAuth 사용자 정보 업데이트 중 오류 발생: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="사용자 정보 업데이트 중 오류가 발생했습니다.")

    if not all([hasattr(user, 'user_id'), hasattr(user, 'email'), hasattr(user, 'role')]):
        logger.error(f"사용자 객체에서 필수 속성 누락: user_id={getattr(user, 'user_id', None)}, email={getattr(user, 'email', None)}, role={getattr(user, 'role', None)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="사용자 정보 처리 중 내부 오류가 발생했습니다.")


    jwt_payload = {
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role,
    }
    app_jwt_token = create_access_token(
        data=jwt_payload,
        expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    redirect_url = f"{FRONTEND_CALLBACK_URL}?access_token={app_jwt_token}&token_type=bearer&user_id={user.user_id}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

@router.post("/logout")
async def logout(response: Response):
    logger.info("로그아웃 요청 수신. 클라이언트 측 토큰 삭제 필요.")
    return {"message": "로그아웃 요청이 처리되었습니다. 클라이언트에서 저장된 토큰을 삭제해주세요."}