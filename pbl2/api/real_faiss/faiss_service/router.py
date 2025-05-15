import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from api.real_faiss.faiss_service import crud, schema
from api.core.auth import get_current_user 
from api.models.ORM import User as MainUser

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", summary="FAISS 서비스 헬스 체크")
async def health_check_faiss_service():
    return {"message": "FAISS service is operational."}

@router.post("/add", response_model=schema.AddResponse, summary="FAISS에 대화 문서 추가")
async def add_documents_to_faiss_endpoint(
    documents: List[schema.DocumentInput],
    current_user: MainUser = Depends(get_current_user)
):
    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided to add.")

    for doc_input in documents:
        if doc_input.user_id != current_user.user_id: 
            raise HTTPException(
                status_code=403,
                detail=f"Document user_id {doc_input.user_id} does not match authenticated user_id {current_user.user_id}."
            )
    try:
        added_ids = await crud.add_faiss_documents(documents)
        return schema.AddResponse(added_ids=added_ids, message=f"Successfully added {len(added_ids)} documents.")
    except ValueError as e:
        logger.error(f"Value error during FAISS document addition: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during FAISS document addition.")
        raise HTTPException(status_code=500, detail="Internal server error in FAISS service.")

@router.post("/history", response_model=schema.ConversationHistoryResponse, summary="세션 ID로 대화 기록 조회 (대화형)")
async def get_session_history_endpoint(
    request: schema.HistoryRequest,
    current_user: MainUser = Depends(get_current_user)
):
    if current_user.user_id != request.user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only request history for your own user_id."
        )
    try:
        conversation_history = crud.get_conversation_history_by_session(request.session_id, request.user_id)
        return conversation_history
    except ValueError as e:
        logger.error(f"Value error fetching history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        logger.exception("Error fetching conversation history.")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation history.")

@router.post("/search_session", response_model=List[schema.SessionSearchResult], summary="세션 내 유사 대화 검색")
async def search_within_session_endpoint(
    query_request: schema.SessionSearchQuery,
    current_user: MainUser = Depends(get_current_user)
):
    if current_user.user_id != query_request.user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only search within your own user_id's sessions."
        )
    try:
        search_results = crud.search_faiss_session(
            session_id=query_request.session_id,
            user_id=query_request.user_id,
            query=query_request.query,
            k=query_request.k
        )
        return search_results
    except ValueError as e:
        logger.error(f"Value error during session search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        logger.exception("Error during session search.")
        raise HTTPException(status_code=500, detail="Session search failed.")