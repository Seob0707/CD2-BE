from fastapi import APIRouter, Depends, HTTPException, status, Query
import httpx
from starlette.config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import user_service
from api.schemas.user_schema import UserOAuthCreate, Token as BaseToken
from api.core.security import create_access_token

config = Config(".env")

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=str)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=str)
GOOGLE_REDIRECT_URI = config("GOOGLE_REDIRECT_URI", cast=str)
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"

router = APIRouter(tags=["OAuth"])

class OAuth2TokenResponse(BaseToken):
    user_id: int

@router.get("/google/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def google_login():
    import secrets
    from urllib.parse import urlencode
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, httponly=True, secure=False, samesite="none", path="/")
    return response

@router.get("/google/callback", response_model=OAuth2TokenResponse)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    from fastapi import Cookie
    oauth_state: str = Cookie(..., alias="oauth_state")
    if state != oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state parameter")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URI,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="토큰 교환 실패")

        google_access_token = token_resp.json().get("access_token")
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {google_access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유저 정보 조회 실패")

        ui = userinfo_resp.json()
        email = ui.get("email")
        nickname = ui.get("name", email)

    user = await user_service.get_user_by_email(db, email)
    if not user:
        dto = UserOAuthCreate(email=email, nickname=nickname)
        user = await user_service.create_oauth_user(db, dto)

    jwt_token = create_access_token(data={"sub": str(user.user_id)})
    return OAuth2TokenResponse(
        access_token=jwt_token,
        token_type="bearer",
        user_id=user.user_id
    )
