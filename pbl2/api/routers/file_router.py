import os
import tempfile
import base64
import httpx 
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as UploadFileDep, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.database import get_db
from api.core.auth import get_current_user
from api.models.ORM import User, Session

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".csv", ".txt"}

def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def simulate_send_to_ai(encoded_data: str):
    """
    인공지능 서버로 전송 준비하는 스텁 함수.
    실제 전송 구현 전까지는 인코딩된 데이터의 일부를 출력합니다.
    """
    ai_server_url = "http://ai-server.example.com/process"
    print(f"AI 서버 전송 준비 - encoded_data (일부): {encoded_data[:100]}...")
    # 실제 전송 예시 (비동기):
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(ai_server_url, json={"data": encoded_data})
    #     response.raise_for_status()
    #     return response.json()

@router.post("/{session_id}/files")
async def upload_file(
    session_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = UploadFileDep(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Session).where(Session.session_id == session_id)
    result = await db.execute(stmt)
    session_obj = result.scalars().first()
    if session_obj is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="해당 세션에 대한 접근 권한이 없습니다.")

    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="허용되지 않는 파일 형식입니다. (jpg, png, pdf, csv, txt만 허용)")

    try:
        file_content = await file.read()
        with tempfile.NamedTemporaryFile(
            delete=False, 
            dir=UPLOAD_DIR, 
            prefix="temp_", 
            suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"임시 파일 생성 오류: {e}")

    try:
        encoded_data = base64.b64encode(file_content).decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 인코딩 오류: {e}")

    background_tasks.add_task(simulate_send_to_ai, encoded_data)

    return {
        "detail": "파일이 성공적으로 처리되었습니다.",
        "temp_file_path": temp_file_path
    }
