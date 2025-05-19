import logging
import uuid
import httpx
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.preference_schemas import PreferenceInput, PreferenceResponse
from api.core.auth import get_current_user
from api.models.ORM import User as MainUser
from api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Message Preference"],
)

AI_SERVER_PREFERENCE_URL = getattr(settings, "AI_SERVER_PREFERENCE_URL", "http://pbl.kro.kr:8000/feedback/{session_id}")
PREFERENCE_DATA_FILE_PATH = getattr(settings, "PREFERENCE_DATA_FILE_PATH", "/app/data/preference_files")
AI_SERVER_SHARED_SECRET = getattr(settings, "AI_SERVER_SHARED_SECRET", None)


@router.post(
    "/submit",
    response_model=PreferenceResponse,
    summary="AI 메시지 선호도 제출 및 AI 서버 연동 (보안 강화)"
)
async def submit_message_preference(
    preference_data: PreferenceInput,
    current_user: MainUser = Depends(get_current_user)
):
    user_id_str = str(current_user.user_id)
    timestamp_utc_iso = datetime.now(timezone.utc).isoformat()

    if not AI_SERVER_SHARED_SECRET:
        logger.error("AI_SERVER_SHARED_SECRET is not configured. Cannot securely communicate with AI server.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application is not configured correctly for secure AI server communication."
        )

    ai_server_payload = {
        "preference_user_id": user_id_str,
        "target_ai_message_id": preference_data.target_message_id,
        "session_identifier": str(preference_data.session_id),
        "user_preference_value": preference_data.rating,
        "preference_text": preference_data.preference_text,
        "preference_timestamp": timestamp_utc_iso
    }

    headers = {
        "X-AI-Server-Shared-Secret": AI_SERVER_SHARED_SECRET
    }

    received_file_content = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(AI_SERVER_PREFERENCE_URL, json=ai_server_payload, headers=headers)
            response.raise_for_status()
            received_file_content = response.content
            logger.info(f"Successfully received data file from AI server for user {user_id_str} after submitting preference for message {preference_data.target_message_id}")

    except httpx.RequestError as exc:
        logger.error(f"Error requesting AI server for preference: {exc!r} for user {user_id_str}, message {preference_data.target_message_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not communicate with the AI server for preference submission: {exc.__class__.__name__}"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
            logger.error(f"AI server denied access (shared secret mismatch?): {exc.response.status_code} for user {user_id_str}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, 
                detail="Failed to authenticate with AI server. Check shared secret."
            )
        logger.error(f"AI server returned an error for preference: {exc.response.status_code} - {exc.response.text} for user {user_id_str}, message {preference_data.target_message_id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI server error during preference processing: {exc.response.status_code}"
        )

    if received_file_content is None:
        logger.error(f"No data file content received from AI server after preference submission for user {user_id_str}, message {preference_data.target_message_id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No data file content received from AI server after preference submission."
        )

    saved_file_path_str = None
    try:
        os.makedirs(PREFERENCE_DATA_FILE_PATH, exist_ok=True)
        msg_id_short = preference_data.target_message_id[:8]
        unique_filename = f"user_{user_id_str}_session_{preference_data.session_id}_msg_{msg_id_short}_pref_{uuid.uuid4()}.dat"
        saved_file_path = os.path.join(PREFERENCE_DATA_FILE_PATH, unique_filename)

        with open(saved_file_path, "wb") as f:
            f.write(received_file_content)
        saved_file_path_str = saved_file_path
        logger.info(f"Successfully saved preference-related data file to {saved_file_path_str} for user {user_id_str}, message {preference_data.target_message_id}")

    except IOError as e:
        logger.error(f"Failed to save preference-related data file to Docker volume: {e!r} for user {user_id_str}, message {preference_data.target_message_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save preference-related data file: {e.__class__.__name__}"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred during preference file saving: {e!r} for user {user_id_str}, message {preference_data.target_message_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during preference file processing: {e.__class__.__name__}"
        )

    return PreferenceResponse(
        message="Preference submitted and data file processed successfully (securely).",
        saved_file_path=saved_file_path_str
    )
