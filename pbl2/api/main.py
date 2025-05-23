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
from api.routers.language_router import router as language_router
from api.routers.token_validation_router import router as token_validation_router
from api.real_faiss.faiss_service.router import router as faiss_actual_router
from api.routers.preference_router import router as preference_router

from api.routers.ai_file_management_router import router as ai_file_management_router

from api.config import settings
from api.real_faiss.faiss_service import crud as faiss_crud

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from api.domain.cleanup_service import cleanup_old_temporary_files

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.API_VERSION
)

scheduler = AsyncIOScheduler()

async def scheduled_cleanup_job():
    logger.info("스케줄된 임시 파일 정리 작업 호출됨...")
    try:
        await cleanup_old_temporary_files()
        logger.info("스케줄된 임시 파일 정리 작업 성공적으로 완료.")
    except Exception as e:
        logger.error(f"스케줄된 임시 파일 정리 작업 중 오류 발생: {e}", exc_info=True)

@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Application startup: Initializing FAISS DB...")
        faiss_crud.load_or_create_faiss_db()
        logger.info("Application startup: FAISS DB initialized successfully.")
    except ValueError as e:
        logger.critical(f"Application startup: CRITICAL - FAISS DB could not be initialized. Service might be unavailable. Error: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Application startup: CRITICAL - An unexpected error occurred during FAISS DB initialization. Error: {e}", exc_info=True)

    try:
        if not os.path.exists(settings.UPLOAD_DIR):
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            logger.info(f"Upload directory '{settings.UPLOAD_DIR}' ensured/created on startup.")
    except Exception as e:
        logger.error(f"Error creating upload directory '{settings.UPLOAD_DIR}' on startup: {e}", exc_info=True)

    try:
        job_interval_hours = settings.CLEANUP_JOB_INTERVAL_HOURS
        scheduler.add_job(scheduled_cleanup_job, 'interval', hours=job_interval_hours, id="periodic_temp_file_cleanup")
        scheduler.start()
        logger.info(f"임시 파일 자동 정리 스케줄러가 시작되었습니다. 실행 간격: {job_interval_hours}시간")
        app.state.scheduler = scheduler
    except Exception as e:
        logger.error(f"스케줄러 시작 중 오류 발생: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'scheduler') and app.state.scheduler.running:
        app.state.scheduler.shutdown()
        logger.info("임시 파일 자동 정리 스케줄러가 정상적으로 종료되었습니다.")

ORIGINS = [
    "http://localhost:5173",
    "https://pbl.kro.kr",
    "https://cd2-fe.vercel.app",
    os.getenv("AI_SERVER_URL_FOR_CORS", settings.AI_SERVER_URL),
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
    secret_key=os.getenv("SESSION_SECRET_KEY", settings.secret_key),
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=settings.environment == "production"
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
app.include_router(faiss_actual_router, prefix="/api/v1/faiss", tags=["FAISS VectorDB Service"])
app.include_router(preference_router, prefix="/api/v1/preference", tags=["Message Preference and AI Data Exchange"])
app.include_router(language_router, prefix="/api/v1/language", tags=["languages"])

app.include_router(ai_file_management_router)