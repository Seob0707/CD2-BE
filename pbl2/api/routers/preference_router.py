import logging
import uuid
import httpx
import os
import hashlib
import hmac
from datetime import datetime, timezone
import json

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Header
from fastapi.responses import FileResponse, JSONResponse

from api.schemas.preference_schemas import (
    PreferenceInput, PreferenceSubmitResponse,
    PreferenceFileReceiveResponse, PreferenceFileSendRequest
)
from api.core.auth import get_current_user, oauth2_scheme
from api.models.ORM import User as MainUser
from api.config import settings

from api.real_faiss.faiss_service import crud

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Message Preference and AI Data Exchange"],
)

PREFERENCE_AI_FILES_STORAGE_PATH = getattr(settings, "PREFERENCE_AI_FILES_STORAGE_PATH", "/app/preference_related_ai_files")
AI_SERVER_SHARED_SECRET = getattr(settings, "AI_SERVER_SHARED_SECRET", None)
AI_SERVER_PREFERENCE_URL_TEMPLATE = getattr(settings,"AI_SERVER_PREFERENCE_URL_TEMPLATE","https://pblai.r-e.kr/feedback/{session_id}" 
)

def verify_hmac_signature(data: bytes, received_signature: str, secret: str) -> bool:
    if not secret:
        logger.error("Shared secret is not configured for HMAC verification.")
        return False
    if not received_signature:
        logger.warning("Received HMAC signature is missing.")
        return False
    computed_signature = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_signature, received_signature)

@router.post(
    "/submit",
    response_model=PreferenceSubmitResponse
)
async def submit_message_preference(
    preference_data: PreferenceInput,
    current_user: MainUser = Depends(get_current_user),
    user_access_token: str = Depends(oauth2_scheme)
):
    user_id_int = current_user.user_id

    if not AI_SERVER_SHARED_SECRET:
        logger.warning("AI_SERVER_SHARED_SECRET (or other auth mechanism for AI server) might still be needed depending on AI server API design.")

    recommand_value = True if preference_data.rating == "like" else False
    
    ai_server_payload = {
        "token": user_access_token, 
        "message_id": preference_data.message_id,
        "recommand": recommand_value,
    }

    headers = {
        "Content-Type": "application/json"
    }
    actual_ai_server_url = AI_SERVER_PREFERENCE_URL_TEMPLATE.format(session_id=preference_data.session_id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(actual_ai_server_url, json=ai_server_payload, headers=headers)
            response.raise_for_status()
            logger.info(
                f"AI server responded with {response.status_code} for preference submission by user {user_id_int}"
            )
    except httpx.RequestError as exc:
        logger.error(f"Error requesting AI server for preference: {exc!r}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not communicate with AI server: {exc.__class__.__name__}"
        )
    except httpx.HTTPStatusError as exc:
        logger.error(f"AI server error for preference: {exc.response.status_code} - {exc.response.text}")
        if exc.response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
             raise HTTPException(
                 status_code=status.HTTP_502_BAD_GATEWAY, 
                 detail="AI server rejected the request. Check signature or credentials."
             )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, 
            detail=f"AI server error: {exc.response.status_code}"
        )
    
    try:
        updated_in_faiss = await crud.update_recommendation_status(
            message_id=preference_data.message_id,
            status=preference_data.rating
        )
        if not updated_in_faiss:
            logger.warning(f"Could not update recommendation_status in FAISS for message {preference_data.message_id}.")
    except Exception as e:
        logger.error(f"An error occurred during FAISS recommendation_status update: {e!r}", exc_info=True)

    return PreferenceSubmitResponse(
        message="Preference notification sent to AI server successfully."
    )

@router.post(
    "/ai_file_upload",
    response_model=PreferenceFileReceiveResponse
)
async def ai_initiated_file_upload(
    session_id: int = Form(...),
    file: UploadFile = File(...),
    x_signature_hmac_sha256: str = Header(..., alias="X-Signature-HMAC-SHA256")
):
    if not AI_SERVER_SHARED_SECRET:
        logger.error("AI_SERVER_SHARED_SECRET is not configured for AI file upload.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Application not configured for secure AI data exchange."
        )

    file_content = await file.read()
    await file.seek(0)

    data_to_sign = file_content
    if not verify_hmac_signature(data_to_sign, x_signature_hmac_sha256, AI_SERVER_SHARED_SECRET):
        logger.warning(f"Invalid HMAC signature for AI file upload, session_id: {session_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid HMAC signature.")

    try:
        os.makedirs(PREFERENCE_AI_FILES_STORAGE_PATH, exist_ok=True)
        
        original_filename = file.filename if file.filename else "ai_data"
        file_extension = os.path.splitext(original_filename)[1] if os.path.splitext(original_filename)[1] else ".dat"
        unique_filename = f"session_{session_id}_ai_push_{uuid.uuid4()}{file_extension}"
        saved_file_path = os.path.join(PREFERENCE_AI_FILES_STORAGE_PATH, unique_filename)

        with open(saved_file_path, "wb") as buffer: 
            buffer.write(file_content)
        
        logger.info(f"AI server pushed file, saved for session_id: {session_id} at {saved_file_path}")
        return PreferenceFileReceiveResponse(
            message="AI-initiated file received and saved successfully.", 
            file_path=saved_file_path
        )
        
    except IOError as e:
        logger.error(f"Failed to save AI-initiated file for session_id {session_id}: {e!r}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to save AI-initiated file."
        )
    except Exception as e:
        logger.error(f"Unexpected error saving AI-initiated file for session_id {session_id}: {e!r}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="An unexpected error occurred while saving AI-initiated file."
        )
    finally:
        await file.close()

@router.post(
    "/request_ai_file",
    response_class=FileResponse
)
async def request_ai_file(
    request_data: PreferenceFileSendRequest,
    x_signature_hmac_sha256: str = Header(..., alias="X-Signature-HMAC-SHA256")
):
    session_id = request_data.session_id

    if not AI_SERVER_SHARED_SECRET:
        logger.error("AI_SERVER_SHARED_SECRET is not configured for AI file request.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Application not configured for secure AI data exchange."
        )

    try:
        payload_bytes = request_data.model_dump_json(sort_keys=True, separators=(',', ':')).encode('utf-8')
    except Exception as e:
        logger.error(f"Error serializing request_data for HMAC verification: {e!r}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid request data format."
        )

    if not verify_hmac_signature(payload_bytes, x_signature_hmac_sha256, AI_SERVER_SHARED_SECRET):
        logger.warning(f"Invalid HMAC signature for AI file request, session_id: {session_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid HMAC signature.")

    potential_files = []
    try:
        target_directory = PREFERENCE_AI_FILES_STORAGE_PATH
        if os.path.exists(target_directory):
            for fname in os.listdir(target_directory):
                if fname.startswith(f"session_{session_id}_ai_push_") and fname.endswith((".json", ".dat")):
                    potential_files.append(os.path.join(target_directory, fname))

        if not potential_files:
            logger.info(f"No AI-initiated file found for session_id: {session_id} to send.")
            return JSONResponse(
                content={"message": f"No AI-initiated file found for session_id: {session_id}"}, 
                status_code=status.HTTP_404_NOT_FOUND
            )

        latest_file = max(potential_files, key=os.path.getmtime)

        logger.info(f"Sending AI-initiated file: {latest_file} for session_id: {session_id}")
        return FileResponse(
            path=latest_file,
            filename=os.path.basename(latest_file),
            media_type='application/octet-stream'
        )
        
    except FileNotFoundError:
        logger.warning(f"File not found for sending (session_id {session_id}) after listing.")
        return JSONResponse(
            content={"message": "Requested AI file not found."}, 
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error sending AI-initiated file for session_id {session_id}: {e!r}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error sending AI-initiated file."
        )