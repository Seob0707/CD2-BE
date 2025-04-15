from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from api.routers import user_router, oauth_router, session_router, file_router, topic_router, search_router, dev_util_router 

app = FastAPI()

ORIGIN = [
    "http://localhost:5173",
    "https://pbl.kro.kr"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/version", tags=["version"])
async def version():
    return {"version": "1.0.0"}

app.include_router(user_router.router, prefix="/api/v1/user", tags=["User"])
app.include_router(oauth_router.router, prefix="/api/v1/oauth", tags=["OAuth"])
app.include_router(session_router.router, prefix="/api/v1/sessions", tags=["Session"])
app.include_router(file_router.router, prefix="/api/v1/sessions", tags=["File"])
app.include_router(topic_router.router, prefix="/api/v1/topics", tags=["Topic"])
app.include_router(search_router.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(dev_util_router.router, prefix="/api/v1", tags=["seed"])