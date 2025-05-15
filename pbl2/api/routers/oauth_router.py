from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
#from fastapi.security import OAuth2PasswordBearer
from authlib.integrations.starlette_client import OAuth
from authlib.oauth2.rfc6749.errors import OAuth2Error
from starlette.config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import timedelta
import logging

from api.database import get_db
from api.domain import user_service
from api.schemas.user_schema import UserOAuthCreate
from api.core.security import create_access_token
from api.models.ORM import User

logger = logging.getLogger(__name__)

config = Config(".env")
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=str)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=str)
REDIRECT_URI = config("GOOGLE_REDIRECT_URI", cast=str)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=30)
FRONTEND_CALLBACK_URL = config("FRONTEND_CALLBACK_URL", cast=str)

oauth = OAuth(config)
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "access_type": "offline"},
)

router = APIRouter(tags=["OAuth"])

@router.get("/login", summary="Google OAuth 로그인 시작")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)

@router.get("/callback", summary="Google OAuth 콜백 처리")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        token_data = await oauth.google.authorize_access_token(request)
    except OAuth2Error as e:
        logger.error(f"Google OAuth 토큰 교환 실패: {e.error} - {e.description}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Google 인증에 실패했습니다: {e.error}")
    google_access_token = token_data.get("access_token")
    if not google_access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="액세스 토큰이 없습니다.")
    user_info = token_data.get("userinfo") or await oauth.google.parse_id_token(request, token_data)
    email = user_info.get("email")
    nickname = user_info.get("name") or email.split("@")[0]
    sub = user_info.get("sub")
    if not all([email, sub]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="필수 사용자 정보가 없습니다.")
    user = await user_service.get_user_by_email(db, email)
    if not user:
        dto = UserOAuthCreate(email=email, nickname=nickname)
        user = await user_service.create_oauth_user(db, dto, "google", sub, token_data.get("refresh_token"))
    else:
        user = await user_service.update_user_oauth_details(db, user, nickname, "google", sub, token_data.get("refresh_token"))
    jwt_payload = {"sub": str(user.user_id), "email": user.email, "role": user.role}
    #app_jwt_token = create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    # JSON으로 토큰 반환
    #return JSONResponse({"access_token": app_jwt_token, "token_type": "bearer"})
    app_jwt_token = create_access_token(data=jwt_payload)
    frontend = FRONTEND_CALLBACK_URL 
    redirect_url = f"{frontend}?access_token={app_jwt_token}&token_type=bearer"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

@router.post("/logout", summary="로그아웃")
async def logout(response: Response):
    response.delete_cookie(key="access_token_cookie", httponly=True, secure=True, samesite="Lax", path="/")
    return {"message": "성공적으로 로그아웃 되었습니다."}
