from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
import httpx, os
from urllib.parse import urlencode
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import user_service
from api.core import security
from api.schemas import user_schema

router = APIRouter()

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI")
FRONTEND_URL         = os.getenv("FRONTEND_URL")

GOOGLE_AUTH_URI      = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI  = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPE                = "email profile"

@router.get("/google/login")
async def google_login():
    params = {
        "response_type": "code",
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "scope":         SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    query_string = urlencode(params)
    auth_url = f"{GOOGLE_AUTH_URI}?{query_string}"
    return RedirectResponse(auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/google/callback")
async def google_callback(
    code: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 에러 파라미터 처리 (등록 URI 불일치 등)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth Error: {error}"
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="구글에서 인가 코드를 받지 못했습니다."
        )

    # 1) code → access_token 교환
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URI, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"토큰 교환 실패: {token_resp.text}"
            )
        access_token = token_resp.json().get("access_token")

        # 2) userinfo 호출
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"사용자 정보 조회 실패: {userinfo_resp.text}"
            )
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")

    # 3) DB에서 사용자 조회 또는 생성
    user = await user_service.get_user_by_email(db, email)
    if not user:
        user = await user_service.create_oauth_user(
            db,
            user_schema.UserOAuthCreate(email=email, nickname=email)
        )

    # 4) JWT 생성
    jwt_token = security.create_access_token(data={"sub": str(user.user_id)})

    # 5) 프론트엔드로 Redirect (토큰 전달)
    redirect_url = f"{FRONTEND_URL}/oauth2/redirect?token={jwt_token}"
    return RedirectResponse(redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
