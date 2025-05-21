import os
import tempfile
import base64
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_db
from api.core.auth import get_current_user
from api.models.ORM import User, Session

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".csv", ".txt"}


MAX_FILE_COUNT    = 3                    # 허용 파일 개수
MAX_FILE_SIZE     = 5  * 1024 * 1024     # 개별 파일 최대 5MiB
MAX_TOTAL_SIZE    = 10 * 1024 * 1024     # 전체 합계 최대 10MiB

def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def simulate_send_to_ai(encoded_data: str):
    ai_server_url = "http://15.164.125.221:8000"
    print(f"AI 서버 전송 준비 - encoded_data (일부): {encoded_data[:100]}...")

@router.post("/{session_id}/files")
async def upload_files(
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
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    if len(files) > MAX_FILE_COUNT:
        raise HTTPException(
            status_code=413,
            detail=f"최대 {MAX_FILE_COUNT}개까지 업로드할 수 있습니다."
        )

    total_size = 0
    saved_paths = []

    for file in files:
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 파일 형식입니다: {file.filename}"
            )

        cl = file.headers.get("content-length")
        if cl and int(cl) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"파일 \"{file.filename}\"이(가) {MAX_FILE_SIZE//(1024*1024)}MiB를 넘습니다."
            )

        content = await file.read()
        size = len(content)
        total_size += size

        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"파일 \"{file.filename}\"이(가) {MAX_FILE_SIZE//(1024*1024)}MiB를 넘습니다."
            )
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"전체 업로드 용량이 {MAX_TOTAL_SIZE//(1024*1024)}MiB를 초과했습니다."
            )

        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=UPLOAD_DIR,
            prefix="temp_",
            suffix=suffix
        ) as tmp:
            tmp.write(content)
            saved_paths.append(tmp.name)

        encoded = base64.b64encode(content).decode("utf-8")
        background_tasks.add_task(simulate_send_to_ai, encoded)

    return {
        "session_id": session_id,
        "detail": f"{len(saved_paths)}개 파일이 성공적으로 업로드되었습니다.",
        "paths": saved_paths
    }
