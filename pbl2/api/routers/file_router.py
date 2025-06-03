import os
import logging
import aiofiles
import base64
import shutil
import asyncio
import time
import hmac
import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.core.auth import get_current_user
from api.models.ORM import User, Session
from api.config import settings
import json

logger = logging.getLogger(__name__)
router = APIRouter()

if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload directory '{settings.UPLOAD_DIR}' created.")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".csv", ".txt"}
MAX_FILE_COUNT = 3
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_TOTAL_SIZE = 10 * 1024 * 1024

def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def generate_hmac(data: str) -> str:
    return base64.b64encode(hmac.new(settings.AI_SERVER_SHARED_SECRET.encode(), data.encode(), hashlib.sha256).digest()).decode()

def verify_hmac(data: str, received_hmac: str) -> bool:
    if not settings.AI_SERVER_SHARED_SECRET:
        return False
    expected_hmac = generate_hmac(data)
    return hmac.compare_digest(expected_hmac, received_hmac)

async def verify_ai_request_signature(request: Request):
    try:
        request_timestamp_str = request.headers.get("X-Signature-Timestamp")
        request_signature = request.headers.get("X-Signature-HMAC-SHA256")

        if not request_timestamp_str or not request_signature:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="시그니처 헤더가 없습니다.")

        current_timestamp = int(time.time())
        request_timestamp = int(request_timestamp_str)
        if abs(current_timestamp - request_timestamp) > 60:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="타임스탬프가 유효하지 않습니다.")

        message_to_sign = f"{request_timestamp_str}.{request.url.path}"
        
        if not verify_hmac(message_to_sign, request_signature):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="시그니처가 일치하지 않습니다.")

    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 형식의 시그니처 헤더입니다.")
    except Exception as e:
        logger.error(f"HMAC 검증 중 오류 발생: {e}")
        raise

@router.post("/{session_id}/files")
async def upload_and_save_files(
    session_id: int,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Session).where(Session.session_id == session_id)
    result = await db.execute(stmt)
    session_obj = result.scalars().first()

    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다.")

    if len(files) > MAX_FILE_COUNT:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"최대 {MAX_FILE_COUNT}개까지 업로드할 수 있습니다.")

    session_upload_dir = os.path.join(settings.UPLOAD_DIR, str(session_id))
    os.makedirs(session_upload_dir, exist_ok=True)

    total_size = 0
    saved_files_info = []

    for file in files:
        if not is_allowed_file(file.filename):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"허용되지 않는 파일 형식입니다: {file.filename}")

        size = file.size
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"빈 파일은 업로드할 수 없습니다: {file.filename}")
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"파일 \"{file.filename}\"이(가) {MAX_FILE_SIZE//(1024*1024)}MiB를 넘습니다.")
        
        total_size += size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"전체 업로드 용량이 {MAX_TOTAL_SIZE//(1024*1024)}MiB를 초과했습니다.")

        file_path = os.path.join(session_upload_dir, file.filename)
        
        try:
            async with aiofiles.open(file_path, "wb") as f:
                content = await file.read()
                await f.write(content)
            saved_files_info.append(file.filename)
            logger.info(f"File '{file.filename}' saved to '{file_path}' for session_id: {session_id}")
        except IOError as e:
            logger.error(f"File saving error for '{file.filename}' in session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파일 '{file.filename}' 저장 중 오류 발생")

    return {
        "session_id": session_id,
        "detail": f"{len(saved_files_info)}개 파일이 성공적으로 업로드되었습니다. AI 서버가 파일을 요청할 준비가 되었습니다.",
        "uploaded_files": saved_files_info
    }

@router.get("/{session_id}/files")
async def get_all_files_for_session(session_id: int, _: dict = Depends(verify_ai_request_signature)):
    session_dir = os.path.join(settings.UPLOAD_DIR, str(session_id))
    
    if not os.path.isdir(session_dir):
        logger.warning(f"AI - Session directory not found for session_id: {session_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 세션을 찾을 수 없거나 업로드된 파일이 없습니다.")

    encoded_files = []
    try:
        filenames = os.listdir(session_dir)
        for filename in filenames:
            file_path = os.path.join(session_dir, filename)
            if os.path.isfile(file_path):
                async with aiofiles.open(file_path, "rb") as f:
                    content_bytes = await f.read()
                
                encoded_content = base64.b64encode(content_bytes).decode("utf-8")
                
                encoded_files.append({
                    "filename": filename,
                    "content_b64": encoded_content
                })

        logger.info(f"AI - Serving all {len(encoded_files)} files for session_id: {session_id}")

        return {
            "session_id": session_id,
            "files": encoded_files
        }

    except Exception as e:
        logger.error(f"AI - Failed to read or encode files for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="세션 파일 처리 중 오류가 발생했습니다.")

@router.delete("/{session_id}/files", status_code=status.HTTP_200_OK)
async def delete_all_files_for_session(session_id: int, _: dict = Depends(verify_ai_request_signature)):
    session_dir = os.path.join(settings.UPLOAD_DIR, str(session_id))

    if not os.path.isdir(session_dir):
        logger.warning(f"AI - Deletion request for non-existent session directory: {session_dir}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 세션 디렉토리를 찾을 수 없습니다.")
    
    try:
        await asyncio.to_thread(shutil.rmtree, session_dir)
        logger.info(f"AI - All files for session {session_id} deleted successfully.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": f"세션 {session_id}의 모든 파일이 성공적으로 삭제되었습니다."}
        )
    except Exception as e:
        logger.error(f"AI - Failed to delete session directory {session_dir}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 {session_id}의 파일 삭제 중 오류가 발생했습니다."
        )