from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
from datetime import datetime
import logging 

from api.routers.user_router import router as user_router
from api.routers.oauth_router import router as oauth_router
from api.routers.session_router import router as session_router
from api.routers.file_router import router as file_router
from api.routers.topic_router import router as topic_router
from api.routers.search_router import router as search_router
from api.routers.dev_util_router import router as dev_util_router
from api.routers.ai_router import router as ai_router
from api.routers.admin_router import router as admin_router

from api.routers.faiss_router import router as faiss_router
from api.routers.token_validation_router import router as token_validation_router
from api.config import settings

from api.real_faiss.faiss_service import crud as faiss_crud
from api.routers.preference_router import router as preference_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) 

app = FastAPI(
    title=settings.PROJECT_NAME if hasattr(settings, 'PROJECT_NAME') else "CD2 Project API",
    description=settings.PROJECT_DESCRIPTION if hasattr(settings, 'PROJECT_DESCRIPTION') else "PBL CD2 프로젝트 백엔드 API 문서입니다.",
    version=settings.API_VERSION if hasattr(settings, 'API_VERSION') else "1.0.0"
)

@app.on_event("startup")
async def startup_event_initialize_faiss():
    try:
        logger.info("Application startup: Initializing FAISS DB...")
        faiss_crud.load_or_create_faiss_db() 
        logger.info("Application startup: FAISS DB initialized successfully.")
    except ValueError as e:
        logger.critical(f"Application startup: CRITICAL - FAISS DB could not be initialized. Service might be unavailable. Error: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Application startup: CRITICAL - An unexpected error occurred during FAISS DB initialization. Error: {e}", exc_info=True)

ORIGINS = [
    "http://localhost:5173",
    "https://pbl.kro.kr",
    "https://cd2-fe.vercel.app",
    os.getenv("AI_SERVER_URL", "http://15.164.125.221:8000"),
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
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-default-fallback-session-secret-key"), 
    max_age=14 * 24 * 3600, 
    same_site="lax", # CSRF 보호를 위해 'lax' 또는 'strict'
    https_only=settings.environment == "production" # 운영 환경에서는 True로 설정
)

@app.get("/version", tags=["Info"], summary="API 버전 및 환경 정보")
async def get_api_version_and_env():
    return {
        "project_version": app.version,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/health", tags=["Info"], summary="API 서버 상태 확인")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

app.include_router(user_router, prefix="/api/v1/user", tags=["User Authentication & Profile"])
app.include_router(oauth_router, prefix="/api/v1/oauth/google", tags=["Google OAuth"])
app.include_router(token_validation_router, prefix="/api/v1/auth/internal", tags=["Internal Token Validation"])
app.include_router(session_router, prefix="/api/v1/sessions", tags=["Session Management"])
app.include_router(file_router, prefix="/api/v1/files", tags=["File Management"])
app.include_router(topic_router, prefix="/api/v1/topics", tags=["Topic Management"])
app.include_router(search_router, prefix="/api/v1/search", tags=["Search Functionality"]) 
app.include_router(dev_util_router, prefix="/api/v1/dev", tags=["Developer Utilities"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["AI Features"])
app.include_router(admin_router, prefix="/api/v1/admin",tags=["Admin"],)
app.include_router(faiss_router, prefix="/api/v1/faiss", tags=["FAISS VectorDB Service"])
app.include_router(preference_router, prefix="/api/v1/preference", tags=["Message Preference"])