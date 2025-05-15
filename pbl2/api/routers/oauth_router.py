from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.responses import RedirectResponse 
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749.errors import OAuth2Error 
from starlette.config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import timedelta

from api.database import get_db
from api.domain import user_service
from api.schemas.user_schema import UserOAuthCreate
from api.core.security import create_access_token
from api.models.ORM import User 
import logging

logger = logging.getLogger(__name__)

try:
    config = Config(".env")
    GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=str)
    GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=str)
    REDIRECT_URI = config("GOOGLE_REDIRECT_URI", cast=str)
    FRONTEND_CALLBACK_URL = config("FRONTEND_CALLBACK_URL", cast=str)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=30)

except Exception as e:
    logger.error(f"환경 변수 로딩 실패: {e}", exc_info=True)
    raise RuntimeError("OAuth 또는 JWT 관련 필수 환경 변수를 로드할 수 없습니다.")


oauth = OAuth(config)
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'access_type': 'offline',
    }
)

router = APIRouter(tags=["OAuth"])

@router.get("/login", summary="Google OAuth 로그인 시작")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)

@router.get("/callback", summary="Google OAuth 콜백 처리")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    try:
        token_data = await oauth.google.authorize_access_token(request)
    except OAuth2Error as e:
        logger.error(f"Google OAuth 토큰 교환 실패: {e.error} - {e.description}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google 인증에 실패했습니다: {e.error}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Google 액세스 토큰 검색 중 알 수 없는 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google 인증 과정에서 내부 오류가 발생했습니다."
        )

    google_access_token = token_data.get('access_token')
    google_refresh_token: Optional[str] = token_data.get('refresh_token')

    if not google_access_token:
        logger.error(f"토큰 응답에 액세스 토큰 없음: {token_data}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="액세스 토큰이 없습니다.")

    user_info_from_google = token_data.get('userinfo')
    if not user_info_from_google:
        try:
            user_info_from_google = await oauth.google.parse_id_token(request, token_data)
        except Exception as e:
            logger.error(f"ID 토큰 파싱 실패: {str(e)}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="사용자 정보를 파싱하는데 실패했습니다.")

    email: Optional[str] = user_info_from_google.get('email')
    nickname: str = user_info_from_google.get('name', user_info_from_google.get('given_name', ''))
    if not nickname and email:
        nickname = email.split('@')[0]

    if not email:
        logger.error("Google 응답에 이메일 정보 없음")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google로부터 이메일 정보를 받을 수 없습니다.")

    oauth_provider_name = "google"
    oauth_user_id_from_google = user_info_from_google.get("sub")
    if not oauth_user_id_from_google:
        logger.error("Google 응답에 사용자 고유 ID(sub) 없음")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google로부터 사용자 고유 ID를 받을 수 없습니다.")


    user = await user_service.get_user_by_email(db, email)

    if not user:
        user_create_dto = UserOAuthCreate(email=email, nickname=nickname)
        user = await user_service.create_oauth_user(
            db,
            user_data=user_create_dto,
            oauth_provider=oauth_provider_name,
            oauth_id=oauth_user_id_from_google,
            refresh_token_val=google_refresh_token
        )
        logger.info(f"새로운 OAuth 사용자 {email} 생성됨. Google ID: {oauth_user_id_from_google}")
    else:
        user = await user_service.update_user_oauth_details(
            db,
            user=user,
            nickname=nickname,
            oauth_provider=oauth_provider_name,
            oauth_id=oauth_user_id_from_google,
            new_refresh_token=google_refresh_token
        )
        logger.info(f"기존 OAuth 사용자 {email} 로그인. Google ID: {oauth_user_id_from_google}")


    jwt_payload = {"sub": str(user.user_id), "email": user.email, "role": user.role}
    app_jwt_token = create_access_token(
        data=jwt_payload,
        expires_delta=timedelta(minutes = JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    response.set_cookie(
        key='access_token_cookie',
        value=app_jwt_token,
        httponly=True,
        secure=True, # 프로덕션에서는 True
        samesite='Lax', # 또는 'Strict'
        path='/',
        max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60 if JWT_ACCESS_TOKEN_EXPIRE_MINUTES else None
    )

    redirect_url = f"{FRONTEND_CALLBACK_URL}#access_token={app_jwt_token}"
    logger.info(f"사용자 {email} 로그인 성공. 프론트엔드 콜백 URL로 리디렉션: {FRONTEND_CALLBACK_URL}")
    return RedirectResponse(redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.post("/logout", summary="로그아웃")
async def logout(response: Response):
    response.delete_cookie(
        key='access_token_cookie',
        secure=True, # 프로덕션에서는 True
        httponly=True,
        samesite='Lax', # 또는 'Strict'
        path='/'
    )
    return {"message": "성공적으로 로그아웃 되었습니다."}
