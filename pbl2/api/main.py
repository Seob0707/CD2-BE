from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os

from api.routers.user_router      import router as user_router
from api.routers.oauth_router     import router as oauth_router
from api.routers.session_router   import router as session_router
from api.routers.file_router      import router as file_router
from api.routers.topic_router     import router as topic_router
from api.routers.search_router    import router as search_router
from api.routers.dev_util_router  import router as dev_util_router
from api.routers.ai_router        import router as ai_router
from api.routers.admin_router     import router as admin_router
from api.routers.faiss_router     import router as faiss_router

app = FastAPI()

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
    secret_key=os.getenv("SESSION_SECRET_KEY", "fallback-secret-key"),
    session_cookie="session",
    max_age=14 * 24 * 3600,   # 14일
    same_site="lax",
    https_only=True           
)

@app.get("/version", tags=["Version"])
async def version():
    return {"version": "1.0.0"}

# User
app.include_router(user_router,    prefix="/api/v1/user",     tags=["User"])
app.include_router(oauth_router,   prefix="/api/v1/oauth/google",    tags=["OAuth"])

# Session & File
app.include_router(session_router, prefix="/api/v1/sessions", tags=["Session"])
app.include_router(file_router,    prefix="/api/v1/files",    tags=["File"])

# Topic, Search, Dev-Utils
app.include_router(topic_router,   prefix="/api/v1/topics",   tags=["Topic"])
app.include_router(search_router,  prefix="/api/v1/search",   tags=["Search"])
app.include_router(dev_util_router,prefix="/api/v1/dev",      tags=["Dev"])

# AI & Admin & Faiss
app.include_router(ai_router)      
app.include_router(admin_router)   
app.include_router(faiss_router,   prefix="/api/v1/faiss",    tags=["Faiss"])
