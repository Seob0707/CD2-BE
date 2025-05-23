import os
import tempfile
import base64
from typing import List, Dict
import logging
import httpx
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.core.auth import get_current_user
from api.models.ORM import User, Session
from api.config import settings

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

async def actual_send_to_ai_and_cleanup(
    session_id: int,
    files_payload_sent_to_ai: List[Dict],
    local_files_info: List[Dict]
):
    ai_processing_url = f"{settings.AI_SERVER_URL}/files/process_batch/{session_id}"
    logger.info(f"AI 서버 ({ai_processing_url})로 세션 ID {session_id}의 파일 배치({len(files_payload_sent_to_ai)}개) 전송 시작")
    
    request_data = {"files": files_payload_sent_to_ai}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ai_processing_url,
                json=request_data,
                timeout=settings.AI_SERVER_TIMEOUT
            )
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"AI 서버 응답 (세션 ID: {session_id} 배치): {response.status_code} - {response_data}")

            if response_data.get("status") == "completed_batch" and response_data.get("session_id") == session_id:
                logger.info(f"세션 ID {session_id}의 파일 배치 AI 처리 완료 확인. 로컬 임시 파일 삭제 시작.")
                deletion_tasks = []
                for local_file_entry in local_files_info:
                    logger.debug(f"삭제 예약: {local_file_entry['local_path']}")
                    deletion_tasks.append(asyncio.to_thread(os.remove, local_file_entry["local_path"]))
                
                results = await asyncio.gather(*deletion_tasks, return_exceptions=True)
                for i, res_del in enumerate(results):
                    target_path = local_files_info[i]["local_path"]
                    if isinstance(res_del, Exception):
                        if isinstance(res_del, FileNotFoundError):
                             logger.warning(f"로컬 임시 파일 삭제 시도 - 파일 없음: {target_path}")
                        else:
                            logger.error(f"로컬 임시 파일 삭제 실패 ({target_path}): {res_del}", exc_info=res_del)
                    else:
                        logger.info(f"로컬 임시 파일 삭제 완료: {target_path}")
            else:
                logger.warning(f"AI 서버가 세션 ID {session_id}의 배치 처리를 완료하지 못했거나 응답이 다릅니다. 로컬 파일 유지. 응답: {response_data}")

    except httpx.HTTPStatusError as e:
        logger.error(f"AI 서버 오류 응답 (세션 ID: {session_id} 배치): {e.response.status_code} - {e.response.text}", exc_info=True)
    except httpx.RequestError as e:
        logger.error(f"AI 서버 요청 실패 (세션 ID: {session_id} 배치): {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"AI 서버 전송 및 후처리 중 예상치 못한 오류 (세션 ID: {session_id} 배치): {str(e)}", exc_info=True)

@router.post("/{session_id}/files")
async def upload_files_save_temp_and_send(
    session_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
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
    if not os.path.exists(session_upload_dir):
        os.makedirs(session_upload_dir, exist_ok=True)
        logger.info(f"Session upload directory '{session_upload_dir}' created for session_id: {session_id}.")

    total_size = 0
    ai_payloads_for_session = [] 
    local_files_to_manage = [] 

    for file in files:
        if not is_allowed_file(file.filename):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"허용되지 않는 파일 형식입니다: {file.filename}")

        content = await file.read()
        await file.seek(0)

        size = len(content)
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"빈 파일은 업로드할 수 없습니다: {file.filename}")
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"파일 \"{file.filename}\"이(가) {MAX_FILE_SIZE//(1024*1024)}MiB를 넘습니다.")
        
        total_size += size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"전체 업로드 용량이 {MAX_TOTAL_SIZE//(1024*1024)}MiB를 초과했습니다.")

        safe_filename = f"{tempfile.NamedTemporaryFile(prefix='', delete=True).name.split(os.sep)[-1]}_{file.filename}"
        file_path = os.path.join(session_upload_dir, safe_filename)

        try:
            with open(file_path, "wb") as f:
                f.write(content)
            local_files_to_manage.append({"original_filename": file.filename, "local_path": file_path})
            logger.info(f"File '{safe_filename}' saved locally to '{file_path}' for session_id: {session_id}")
        except IOError as e:
            logger.error(f"File saving error for '{safe_filename}' in session {session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파일 '{file.filename}' 저장 중 오류 발생")

        encoded_content = base64.b64encode(content).decode("utf-8")
        ai_payloads_for_session.append({"filename": file.filename, "content_b64": encoded_content})

    if ai_payloads_for_session:
        background_tasks.add_task(
            actual_send_to_ai_and_cleanup,
            session_id,
            ai_payloads_for_session,
            local_files_to_manage
        )

    return {
        "session_id": session_id,
        "detail": f"{len(local_files_to_manage)}개 파일이 임시 저장되었고, AI 서버로 전송 및 후처리가 예약되었습니다.",
        "uploaded_files": [info["original_filename"] for info in local_files_to_manage]
    }