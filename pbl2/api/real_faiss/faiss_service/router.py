import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from api.real_faiss.faiss_service import crud, schema
from api.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="헬스 체크")
async def healthcheck():
    return {"message": "FAISS service is running."}

@router.post("/add", response_model=schema.AddResponse, summary="대화 기록 추가")
async def add_documents_endpoint(
    documents: List[schema.DocumentInput],
    _=Depends(get_current_user)
):
    if not documents:
        raise HTTPException(400, "No documents provided")
    try:
        added_ids = await crud.add_faiss_documents(documents)
        return schema.AddResponse(added_ids=added_ids, message=f"Added {len(added_ids)} docs")
    except ValueError as e:
        logger.error("add error", exc_info=True)
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.exception("add unexpected")
        raise HTTPException(500, "Internal error")

@router.post("/history", response_model=schema.HistoryResponse, summary="대화 기록 조회")
async def get_history_endpoint(
    request: schema.HistoryRequest,
    current_user=Depends(get_current_user)
):
    if current_user.user_id != request.user_id:
        raise HTTPException(403, "Unauthorized")
    try:
        hist = crud.get_faiss_history(request.session_id, request.user_id)
        return schema.HistoryResponse(history=hist)
    except Exception as e:
        logger.exception("history error")
        raise HTTPException(500, "Failed to fetch history")

@router.post("/search_session", response_model=List[schema.SessionSearchResult], summary="세션 내 유사 대화 검색")
async def search_session_endpoint(
    query: schema.SessionSearchQuery,
    current_user=Depends(get_current_user)
):
    if current_user.user_id != query.user_id:
        raise HTTPException(403, "Unauthorized")
    try:
        results = crud.search_faiss_session(
            session_id=query.session_id,
            user_id=query.user_id,
            query=query.query,
            k=query.k
        )
        return results
    except Exception as e:
        logger.exception("search error")
        raise HTTPException(500, "Search failed")
