from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.schemas import session_schema
from api.domain import session_service
from api.core.auth import get_current_user
from api.models.ORM import User

router = APIRouter()

@router.post("/", response_model=session_schema.SessionOut)
async def create_session(
    session_data: session_schema.SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await session_service.create_session(db, current_user.user_id, session_data)

@router.get("/", response_model=list[session_schema.SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await session_service.get_all_sessions(db, current_user.user_id)

@router.get("/{session_id}", response_model=session_schema.SessionOut)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    return session_obj

@router.put("/{session_id}", response_model=session_schema.SessionOut)
async def update_session(
    session_id: int,
    update_data: session_schema.SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    return await session_service.update_session(db, session_id, update_data)

@router.delete("/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    await session_service.delete_session(db, session_id)
    return {"detail": "세션이 삭제되었습니다."}


@router.post("/{session_id}/topics", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_topic_to_existing_session(
    session_id: int,
    topic_data: session_schema.SessionTopicAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_obj = await session_service.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    if session_obj.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    return await session_service.add_topic_to_session(db, session_id, topic_data.topic_id)


@router.delete("/user/all", status_code=status.HTTP_200_OK, summary="모든 세션 삭제")
async def delete_all_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) #
):
    deleted_count = await session_service.delete_all_sessions_for_user(db, current_user.user_id) 
    if deleted_count == 0:
        return {"detail": "삭제할 사용자의 세션이 없습니다."}
    return {"detail": f"총 {deleted_count}개의 세션이 삭제되었습니다."}