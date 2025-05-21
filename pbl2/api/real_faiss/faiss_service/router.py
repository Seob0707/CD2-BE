import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud
from . import schema
from api.core.auth import get_current_user
from api.models.ORM import User as MainUser
from api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    #tags=["FAISS Service Operations"],
)

@router.get("/health", response_model=dict)
async def health_check_faiss_service():
    if crud.db is None or not hasattr(crud.db, 'index'):
        return {"status": "unhealthy", "message": "FAISS DB not initialized or index is missing."}
    return {"status": "ok", "message": "FAISS service is operational."}


@router.post("/add", response_model=schema.AddResponse, status_code=status.HTTP_201_CREATED)
async def add_documents_to_faiss_endpoint(
    documents: List[schema.DocumentInput],
    current_user: MainUser = Depends(get_current_user)
):
    if not documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents provided to add.")
    for doc_input in documents:
        if doc_input.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Document user_id {doc_input.user_id} does not match authenticated user_id {current_user.user_id}."
            )
    try:
        added_ids = await crud.add_faiss_documents(documents)
        return schema.AddResponse(added_ids=added_ids, message=f"Successfully added {len(added_ids)} messages.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error in FAISS service.")


@router.post("/history", response_model=schema.ConversationHistoryResponse)
async def get_session_history_endpoint(
    request: schema.HistoryRequest,
    current_user: MainUser = Depends(get_current_user),
    db_sql: AsyncSession = Depends(get_db)
):
    if current_user.user_id != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only request history for your own user_id."
        )
    try:
        conversation_history = await crud.get_conversation_history_by_session(
            session_id=request.session_id,
            user_id=request.user_id,
            db_sql=db_sql
        )
        return conversation_history
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch conversation history.")


@router.post("/search/session", response_model=List[schema.SessionSearchResult])
async def search_within_session_endpoint(
    query_request: schema.SessionSearchQuery,
    current_user: MainUser = Depends(get_current_user)
):
    if current_user.user_id != query_request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"FAISS DB Service Unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session search failed.")


@router.post(
    "/search/keyword/sessions",
    response_model=List[schema.ConversationHistoryResponse]
)
async def search_sessions_by_keyword_endpoint(
    request: schema.KeywordSearchRequest,
    current_user: MainUser = Depends(get_current_user),
    db_sql: AsyncSession = Depends(get_db)
):
    if not request.keyword or not request.keyword.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyword cannot be empty.")
    try:
        sessions_history = await crud.get_sessions_by_keyword(
            user_id=current_user.user_id,
            keyword=request.keyword,
            db_sql=db_sql
        )
        return sessions_history
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Service Unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during keyword session search.")
