from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
from datetime import datetime

from api.routers.user_router import router as user_router
from api.routers.oauth_router import router as oauth_router
from api.routers.faiss_router import router as faiss_router
from api.routers.token_validation_router import router as token_validation_router
from api.config import settings 

app = FastAPI(
    title="CD2 Project API",
    description="PBL CD2 프로젝트 백엔드 API 문서입니다.",
    version="1.0.0"
)

ORIGINS = [
    "http://localhost:5173",
    "https://pbl.kro.kr",
    "https://cd2-fe.vercel.app",
    "http://15.164.125.221:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-fallback-session-secret-key-here"),
    session_cookie="user_session_id",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=False # 로컬 개발시는 False 실제 운영시는 True 
)

@app.get("/version", tags=["Info"], summary="API 버전 정보")
async def get_api_version():
    return {"project_version": app.version, "api_build_date": "2025-05-15"}

app.include_router(user_router, prefix="/api/v1/user", tags=["User Authentication & Profile"])
app.include_router(oauth_router, prefix="/api/v1/oauth/google", tags=["Google OAuth"])
app.include_router(
    token_validation_router,
    prefix="/api/v1/auth/internal",
    tags=["Internal Token Validation"]
)
app.include_router(faiss_router, prefix="/api/v1/faiss", tags=["Faiss Management"])

@app.get("/health", tags=["Info"], summary="API 상태 확인")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}