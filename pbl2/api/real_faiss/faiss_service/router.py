import logging
from typing import List, Optional, Union
from fastapi import APIRouter, HTTPException, Depends, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud
from . import schema
from api.core.auth import get_current_user
from api.core.security import verify_hmac_signature, serialize_pydantic_for_hmac
from api.models.ORM import User as MainUser
from api.database import get_db
from api.config import settings

router = APIRouter()

async def get_current_user_or_ai(
    authorization: Optional[str] = Header(None),
    x_signature_hmac_sha256: Optional[str] = Header(None, alias="X-Signature-HMAC-SHA256"),
    db_sql: AsyncSession = Depends(get_db)
) -> Union[MainUser, dict]:
    if x_signature_hmac_sha256:
        if not settings.AI_SERVER_SHARED_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI server communication not configured."
            )
        return {"is_ai_server": True, "user_id": "ai_server"}
    
    if authorization:
        return await get_current_user(authorization.replace("Bearer ", ""), db_sql)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No valid authentication provided"
    )

@router.get("/health", response_model=dict)
async def health_check_faiss_service():
    if crud.db is None or not hasattr(crud.db, 'index'):
        return {"status": "unhealthy", "message": "FAISS DB not initialized or index is missing."}
    return {"status": "ok", "message": "FAISS service is operational."}

@router.post("/add", response_model=schema.AddResponse, status_code=status.HTTP_201_CREATED)
async def add_documents_to_faiss_endpoint(
    documents: List[schema.DocumentInput],
    current_user_or_ai: Union[MainUser, dict] = Depends(get_current_user_or_ai),
    db_sql: AsyncSession = Depends(get_db),
    request: Request = None,
    x_signature_hmac_sha256: Optional[str] = Header(None, alias="X-Signature-HMAC-SHA256")
):
    is_ai_request = isinstance(current_user_or_ai, dict) and current_user_or_ai.get("is_ai_server")
    
    if is_ai_request:
        logging.info(f"=== AI FAISS ADD REQUEST DEBUG ===")
        logging.info(f"Documents count: {len(documents)}")
        logging.info(f"Client IP: {request.client.host if request and request.client else 'Unknown'}")
        logging.info(f"=====================================")
        
        try:
            payload_json = serialize_pydantic_for_hmac(documents)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request data format."
            )
        
        if not verify_hmac_signature(payload_json, x_signature_hmac_sha256):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid HMAC signature."
            )
        
        success_message = f"Successfully added {{}} messages via AI server."
    else:
        current_user = current_user_or_ai
        logging.info(f"=== FAISS ADD REQUEST DEBUG ===")
        logging.info(f"User ID: {current_user.user_id}")
        logging.info(f"Documents count: {len(documents)}")
        logging.info(f"Client IP: {request.client.host if request and request.client else 'Unknown'}")
        logging.info(f"================================")
        
        for doc_input in documents:
            if doc_input.user_id != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Document user_id {doc_input.user_id} does not match authenticated user_id {current_user.user_id}."
                )
        
        success_message = f"Successfully added {{}} messages."
    
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents provided to add."
        )
    
    try:
        added_ids = await crud.add_faiss_documents(documents, db_sql)
        return schema.AddResponse(
            added_ids=added_ids, 
            message=success_message.format(len(added_ids))
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"FAISS DB Service Unavailable: {str(e)}"
        )
    except Exception as e:
        logging.error(f"FAISS add error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal server error in FAISS service."
        )

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

@router.post("/search/keyword/sessions", response_model=List[schema.SessionSummaryResponse])
async def search_sessions_by_keyword_endpoint(
    request: schema.KeywordSearchRequest,
    current_user: MainUser = Depends(get_current_user),
    db_sql: AsyncSession = Depends(get_db)
):
    if not request.keyword or not request.keyword.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyword cannot be empty.")
    try:
        sessions_summary = await crud.get_sessions_by_keyword(
            user_id=current_user.user_id,
            keyword=request.keyword,
            db_sql=db_sql
        )
        return sessions_summary
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
    if not settings.AI_SERVER_SHARED_SECRET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application not configured for secure AI server communication.")
    
    try:
        payload_json = serialize_pydantic_for_hmac(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request data format.")
    
    if not verify_hmac_signature(payload_json, x_signature_hmac_sha256):
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