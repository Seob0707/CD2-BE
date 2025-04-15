from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.database import get_db
from api.models.ORM import Session, Topic, TopicSession, User
from api.schemas.session_schema import SessionOut
from api.schemas.topic_schema import TopicSearchOut
from api.core.auth import get_current_user

router = APIRouter()

@router.get("/sessions", response_model=list[SessionOut])
async def search_sessions(
    query: str = Query(..., description="검색어 (세션 제목 또는 주제 이름에 포함된 단어)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt_title = select(Session.session_id).where(
        Session.user_id == current_user.user_id,
        Session.title.ilike(f"%{query}%")
    )
    result_title = await db.execute(stmt_title)
    session_ids_title = {row[0] for row in result_title.all()}

    stmt_topic = select(Topic.topic_id).where(
        Topic.topic_name.ilike(f"%{query}%")
    )
    result_topic = await db.execute(stmt_topic)
    topic_ids = [row[0] for row in result_topic.all()]

    session_ids_topic = set()
    if topic_ids:
        stmt_topic_session = select(TopicSession.session_id).where(
            TopicSession.topic_id.in_(topic_ids)
        )
        result_topic_session = await db.execute(stmt_topic_session)
        session_ids_topic = {row[0] for row in result_topic_session.all()}

    combined_session_ids = session_ids_title | session_ids_topic

    if not combined_session_ids:
        return []

    stmt_sessions = (
        select(Session)
        .where(
            Session.session_id.in_(combined_session_ids),
            Session.user_id == current_user.user_id
        )
        .order_by(Session.created_at.desc())
    )
    result_sessions = await db.execute(stmt_sessions)
    sessions = result_sessions.scalars().all()

    return sessions

@router.get("/topics", response_model=list[TopicSearchOut])
async def search_topics(
    query: str = Query(..., description="검색어 (주제 이름에 포함된 단어)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Topic).where(
        Topic.topic_name.ilike(f"%{query}%")
    )
    result = await db.execute(stmt)
    topics = result.scalars().all()
    return topics
