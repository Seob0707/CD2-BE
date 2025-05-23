from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Annotated
from api.domain import ai_service
from api.config import settings

from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.domain import session_service 

import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    
)

async def verify_backend_internal_api_key(x_backend_internal_api_key: Annotated[str | None, Header()] = None):
    if not settings.BACKEND_INTERNAL_API_KEY:
        logger.error("BACKEND_INTERNAL_API_KEY is not configured on this server.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API endpoint not properly configured."
        )
    if not x_backend_internal_api_key or x_backend_internal_api_key != settings.BACKEND_INTERNAL_API_KEY:
        logger.warning(f"Invalid or missing X-Backend-Internal-Api-Key header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication key for internal API."
        )
    return True

@router.delete("/sessions/{session_id}/files/specific/{filename}",
                status_code=status.HTTP_200_OK,
                summary="내부용: AI 서버의 특정 세션 내 특정 파일 삭제",
                dependencies=[Depends(verify_backend_internal_api_key)])
async def internal_delete_specific_ai_file(session_id: int, filename: str, db: AsyncSession = Depends(get_db)):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        logger.warning(f"Request to delete AI file for non-existent session {session_id} in backend DB. Proceeding with AI server request for file '{filename}'.")


    logger.info(f"Internal API triggered to delete AI file '{filename}' in session {session_id}")
    try:
        ai_response = await ai_service.delete_specific_file_from_ai_server_internal(session_id=session_id, filename=filename)
        if ai_response is None:
             return {"detail": f"AI 서버의 파일 '{filename}'(세션: {session_id}) 삭제 요청이 성공적으로 처리되었습니다 (내용 없음)."}
        return {"detail": f"AI 서버의 파일 '{filename}'(세션: {session_id}) 삭제 요청 결과 수신.", "ai_server_response": ai_response}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"AI 서버 특정 파일 삭제 오류: {e.response.text}")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ve))
    except Exception as e:
        logger.error(f"Error (internal API) requesting specific AI file deletion for session {session_id}, file {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI 서버 특정 파일 삭제 요청 중 내부 오류 발생: {str(e)}")

@router.delete("/sessions/{session_id}/files/all",
                status_code=status.HTTP_200_OK,
                summary="내부용: AI 서버의 특정 세션 내 모든 파일 일괄 삭제",
                dependencies=[Depends(verify_backend_internal_api_key)])
async def internal_delete_all_files_for_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        logger.warning(f"Request to delete all AI files for non-existent session {session_id} in backend DB. Proceeding with AI server request.")
        

    logger.info(f"Internal API triggered to delete ALL files for session {session_id} from AI server.")
    try:
        ai_response = await ai_service.delete_all_files_for_session_from_ai_server_internal(session_id=session_id)
        if ai_response is None:
             return {"detail": f"AI 서버의 세션 {session_id} 내 모든 파일 일괄 삭제 요청이 성공적으로 처리되었습니다 (내용 없음)."}
        return {"detail": f"AI 서버의 세션 {session_id} 내 모든 파일 일괄 삭제 요청 결과 수신.", "ai_server_response": ai_response}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"AI 서버 세션 파일 일괄 삭제 오류: {e.response.text}")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ve))
    except Exception as e:
        logger.error(f"Error (internal API) requesting bulk AI file deletion for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI 서버 세션 파일 일괄 삭제 요청 중 내부 오류 발생: {str(e)}")

@router.delete("/files/all_temporary",
                status_code=status.HTTP_200_OK,
                summary="내부용: AI 서버의 모든 백엔드 전송 임시 파일 일괄 삭제",
                dependencies=[Depends(verify_backend_internal_api_key)])
async def internal_delete_all_temporary_ai_files():
    logger.info(f"Internal API triggered to delete ALL backend-sent temporary files from AI server.")
    try:
        ai_response = await ai_service.delete_all_backend_sent_files_from_ai_server_internal()
        if ai_response is None:
             return {"detail": "AI 서버의 모든 백엔드 전송 임시 파일 일괄 삭제 요청이 성공적으로 처리되었습니다 (내용 없음)."}
        return {"detail": "AI 서버의 모든 백엔드 전송 임시 파일 일괄 삭제 요청 결과 수신.", "ai_server_response": ai_response}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"AI 서버 일괄 파일 삭제 오류: {e.response.text}")
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ve))
    except Exception as e:
        logger.error(f"Error (internal API) requesting bulk AI file deletion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI 서버 일괄 파일 삭제 요청 중 내부 오류 발생: {str(e)}")