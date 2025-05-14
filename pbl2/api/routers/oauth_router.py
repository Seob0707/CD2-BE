from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse
import httpx
import secrets
from urllib.parse import urlencode
from starlette.config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import user_service
from api.schemas import user_schema
from api.core import security

config = Config(".env")

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", cast=str)
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", cast=str)
GOOGLE_REDIRECT_URI = config("GOOGLE_REDIRECT_URI", cast=str)
FRONTEND_URL = config("FRONTEND_URL", cast=str)

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPE = "openid email profile"

router = APIRouter()

@router.get("/google/login")
async def google_login():
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    auth_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"
    response = RedirectResponse(auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie("oauth_state", state, httponly=True, secure=True)
    return response

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(None),
    state: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    cookie_state = request.cookies.get("oauth_state")
    if not state or state != cookie_state or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state or missing code")
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URI, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange failed")
        access_token = token_resp.json().get("access_token")
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Userinfo request failed")
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
    user = await user_service.get_user_by_email(db, email)
    if not user:
        user = await user_service.create_oauth_user(db, user_schema.UserOAuthCreate(email=email, nickname=email))
    jwt_token = security.create_access_token(data={"sub": str(user.user_id)})
    response = RedirectResponse(FRONTEND_URL, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie("access_token", jwt_token, httponly=True, secure=True)
    return response
