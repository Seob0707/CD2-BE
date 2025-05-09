from fastapi import APIRouter, HTTPException
from api.real_faiss.faiss_service.router import router as _svc_router
from api.real_faiss.faiss_service import crud, schema

router = APIRouter()

router.include_router(_svc_router, prefix="", tags=["Faiss"])

@router.post("/search")
async def search(query: schema.Query):
    try:
        return crud.do_faiss_search(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))