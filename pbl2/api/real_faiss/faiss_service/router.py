import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud
from . import schema
from api.core.auth import get_current_user
from api.models.ORM import User as MainUser
from api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
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

@router.patch("/message", response_model=schema.MessageUpdateResponse)
async def update_message_content(
    request: schema.MessageUpdateRequest,
    current_user: MainUser = Depends(get_current_user)
):
    if crud.db is None or not hasattr(crud.db.docstore, '_dict'):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="FAISS service is not available.")

    message_id = request.message_id
    if message_id not in crud.db.docstore._dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Message with message_id '{message_id}' not found.")

    doc_metadata = crud.db.docstore._dict[message_id].metadata
    if doc_metadata.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to edit this message.")

    success = await crud.update_faiss_document(message_id, request.new_page_content)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update message.")
        
    return schema.MessageUpdateResponse(message_id=message_id, message="Message updated successfully.")


@router.delete("/message/{message_id}", response_model=schema.MessageDeleteResponse)
async def delete_message(
    message_id: str,
    current_user: MainUser = Depends(get_current_user)
):
    if crud.db is None or not hasattr(crud.db.docstore, '_dict'):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="FAISS service is not available.")

    if message_id not in crud.db.docstore._dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Message with message_id '{message_id}' not found.")
        
    doc_metadata = crud.db.docstore._dict[message_id].metadata
    if doc_metadata.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this message.")
        
    success = await crud.delete_faiss_document(message_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete message.")

    return schema.MessageDeleteResponse(message_id=message_id, message="Message deleted successfully.")

@router.post("/ai-update", response_model=schema.AIMessageUpdateResponse)
async def ai_update_message(
    request: schema.AIMessageUpdateRequest,
    x_signature_hmac_sha256: str = Header(..., alias="X-Signature-HMAC-SHA256")
):
    if not crud.AI_SERVER_SHARED_SECRET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application not configured for secure AI server communication.")
    
    payload_bytes = request.model_dump_json(sort_keys=True, separators=(',', ':')).encode('utf-8')
    if not crud.verify_hmac_signature(payload_bytes, x_signature_hmac_sha256, crud.AI_SERVER_SHARED_SECRET):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid HMAC signature.")

    success = await crud.ai_update_document(
        message_id=request.message_id,
        new_page_content=request.new_page_content,
        new_evaluation_indices=request.new_evaluation_indices,
        new_recommendation_status=request.new_recommendation_status
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update message via AI request.")
        
    return schema.AIMessageUpdateResponse(message_id=request.message_id, message="Message updated successfully by AI server.")