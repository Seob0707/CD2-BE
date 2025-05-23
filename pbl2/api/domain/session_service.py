import os
import shutil
import logging
import httpx
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from fastapi import HTTPException

from api.models.ORM import Session, Topic, TopicSession
from sqlalchemy.orm import selectinload
from api.config import settings

logger = logging.getLogger(__name__)

async def _delete_directory_async(path: str):
    try:
        await asyncio.to_thread(shutil.rmtree, path)
        logger.info(f"Directory '{path}' deleted successfully asynchronously.")
    except FileNotFoundError:
        logger.warning(f"Attempted to delete directory '{path}', but it was not found.")
    except Exception as e:
        logger.error(f"Error deleting directory '{path}' asynchronously: {e}", exc_info=True)

async def delete_session_local_files(session_id: int):
    session_upload_dir = os.path.join(settings.UPLOAD_DIR, str(session_id))
    if os.path.exists(session_upload_dir) and os.path.isdir(session_upload_dir):
        await _delete_directory_async(session_upload_dir)
    else:
        logger.info(f"No local file directory found for session {session_id} at '{session_upload_dir}'. Nothing to delete.")

async def request_ai_server_delete_session_data(session_id: int):
    ai_cleanup_url = f"{settings.AI_SERVER_URL}/cleanup/session/{session_id}"
    logger.info(f"AI 서버 ({ai_cleanup_url})에 세션 {session_id} 데이터 삭제 요청 시작")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(ai_cleanup_url, timeout=settings.AI_SERVER_TIMEOUT)
            response.raise_for_status()
            logger.info(f"AI 서버에 세션 {session_id} 데이터 삭제 요청 성공: {response.status_code} - {response.text}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"AI 서버에서 세션 {session_id} 데이터를 찾을 수 없음 (404): {e.response.text}")
        else:
            logger.error(f"AI 서버 데이터 삭제 요청 오류 (세션 {session_id}): {e.response.status_code} - {e.response.text}", exc_info=True)
    except httpx.RequestError as e:
        logger.error(f"AI 서버 데이터 삭제 요청 실패 (세션 {session_id}): {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"AI 서버 데이터 삭제 중 예상치 못한 오류 (세션 {session_id}): {str(e)}", exc_info=True)

async def create_session(db: AsyncSession, user_id: int, session_data) -> Session:
    title = session_data.title
    if session_data.topic_id:
        result = await db.execute(select(Topic).where(Topic.topic_id == session_data.topic_id))
        topic_obj = result.scalars().first()
        if not topic_obj:
            raise HTTPException(status_code=404, detail="선택한 주제를 찾을 수 없습니다.")
        if not title:
            title = topic_obj.topic_name
    
    if not title:
        title = "Untitled Session"

    new_session = Session(user_id=user_id, title=title)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    if session_data.topic_id:
        new_topic_session = TopicSession(topic_id=session_data.topic_id, session_id=new_session.session_id)
        db.add(new_topic_session)
        await db.commit()
    
    stmt = (
        select(Session)
        .options(selectinload(Session.topics))
        .where(Session.session_id == new_session.session_id)
    )
    result = await db.execute(stmt)
    created_session_with_details = result.unique().scalars().first()
    return created_session_with_details if created_session_with_details else new_session

async def get_all_sessions(db: AsyncSession, user_id: int):
    stmt = (
        select(Session)
        .options(selectinload(Session.topics))
        .where(Session.user_id == user_id)
        .order_by(Session.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.unique().scalars().all()

async def get_session_by_id(db: AsyncSession, session_id: int):
    stmt = (
        select(Session)
        .options(selectinload(Session.topics))
        .where(Session.session_id == session_id)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().first()

async def update_session(db: AsyncSession, session_id: int, update_data) -> Session:
    session_obj = await get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    if update_data.title is not None:
        session_obj.title = update_data.title
    
    await db.commit()
    await db.refresh(session_obj, attribute_names=['topics'])
    return session_obj

async def delete_session(db: AsyncSession, session_id: int):
    session_obj = await db.get(Session, session_id)
    if not session_obj:
        logger.warning(f"세션 삭제 시도: 세션 ID {session_id}를 찾을 수 없습니다.")
        return

    await db.delete(session_obj)
    await db.commit()
    logger.info(f"세션 ID {session_id}가 데이터베이스에서 삭제되었습니다.")

    await delete_session_local_files(session_id)
    await request_ai_server_delete_session_data(session_id)

async def delete_all_sessions_for_user(db: AsyncSession, user_id: int) -> int:
    stmt_select_ids = select(Session.session_id).where(Session.user_id == user_id)
    result_ids = await db.execute(stmt_select_ids)
    session_ids_to_delete = result_ids.scalars().all()

    if not session_ids_to_delete:
        logger.info(f"사용자 ID {user_id}에 대해 삭제할 세션이 없습니다.")
        return 0
    
    deleted_count = 0
    for session_id_val in session_ids_to_delete: 
        session_obj = await db.get(Session, session_id_val)
        if session_obj:
            await db.delete(session_obj)
            deleted_count += 1
    
    if deleted_count > 0:
        await db.commit()
        logger.info(f"사용자 ID {user_id}의 세션 {deleted_count}개가 데이터베이스에서 삭제되었습니다.")

    tasks = []
    for session_id_val in session_ids_to_delete: 
        tasks.append(delete_session_local_files(session_id_val))
        tasks.append(request_ai_server_delete_session_data(session_id_val))
    
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                related_session_id = session_ids_to_delete[i//2] 
                logger.error(f"세션 {related_session_id}의 파일 또는 AI 데이터 삭제 중 오류: {res}", exc_info=res)

    return deleted_count

async def add_topic_to_session(db: AsyncSession, session_id: int, topic_id: int) -> dict:
    session_obj = await get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    topic_obj_result = await db.execute(select(Topic).where(Topic.topic_id == topic_id))
    topic_obj = topic_obj_result.scalars().first()
    if not topic_obj:
        raise HTTPException(status_code=404, detail="주제를 찾을 수 없습니다.")
    
    existing_topic_session_result = await db.execute(
        select(TopicSession).where(
            TopicSession.session_id == session_id,
            TopicSession.topic_id == topic_id
        )
    )
    if existing_topic_session_result.scalars().first():
        raise HTTPException(status_code=400, detail="이 주제는 이미 추가되어 있습니다.")
    
    new_topic_session = TopicSession(topic_id=topic_id, session_id=session_id)
    db.add(new_topic_session)
    await db.commit()
    return {"detail": f"세션 '{session_obj.title}'에 주제 '{topic_obj.topic_name}'이(가) 성공적으로 추가되었습니다."}