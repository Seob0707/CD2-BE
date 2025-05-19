import logging
from fastapi import APIRouter
from api.real_faiss.faiss_service.router import router as _svc_router

logger = logging.getLogger(__name__)

router = APIRouter()

router.include_router(_svc_router, prefix="")
