from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
import httpx
import os
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import user_service
from api.core import security
from api.schemas import user_schema

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")  

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPE = "email profile"

@router.get("/google/login")
async def google_login():
    auth_url = (
        f"{GOOGLE_AUTH_URI}"
        f"?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&scope={SCOPE}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return RedirectResponse(auth_url)

@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        token_resp = await client.post(GOOGLE_TOKEN_URI, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"구글에서 토큰 발급에 실패하였습니다: {token_resp.text}"
            )
        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="구글 access token이 없습니다."
            )

        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_resp = await client.get(GOOGLE_USERINFO_URI, headers=headers)
        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"구글에서 사용자 정보를 가져오는데 실패하였습니다: {userinfo_resp.text}"
            )
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        nickname = email

    existing_user = await user_service.get_user_by_email(db, email)
    if not existing_user:
        oauth_user_data = user_schema.UserOAuthCreate(email=email, nickname=nickname)
        new_user = await user_service.create_oauth_user(db, oauth_user_data)
        user = new_user
    else:
        user = existing_user

    jwt_token = security.create_access_token(data={"sub": str(user.user_id)})

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user_id": user.user_id
    }

