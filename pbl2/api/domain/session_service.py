from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from api.models.ORM import Session, Topic, TopicSession
from sqlalchemy.orm import selectinload, joinedload

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
        title = "Untitled"
    new_session = Session(user_id=user_id, title=title)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    if session_data.topic_id:
        new_topic_session = TopicSession(topic_id=session_data.topic_id, session_id=new_session.session_id)
        db.add(new_topic_session)
        await db.commit()
    return new_session

async def get_all_sessions(db: AsyncSession, user_id: int):
    stmt = (
        select(Session)
        .options(selectinload(Session.topics))
        .where(Session.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().all()

async def get_session_by_id(db: AsyncSession, session_id: int):
    stmt = (
        select(Session)
        .options(selectinload(Session.topics), selectinload(Session.topic_sessions))
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
    await db.refresh(session_obj)
    return session_obj

async def delete_session(db: AsyncSession, session_id: int):
    session_obj = await db.get(Session, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    await db.delete(session_obj)
    await db.commit()

async def add_topic_to_session(db: AsyncSession, session_id: int, topic_id: int) -> dict:
    
    session_obj = await get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    result = await db.execute(select(Topic).where(Topic.topic_id == topic_id))
    topic_obj = result.scalars().first()
    if not topic_obj:
        raise HTTPException(status_code=404, detail="주제를 찾을 수 없습니다.")
    
    result = await db.execute(
        select(TopicSession).where(
            TopicSession.session_id == session_id,
            TopicSession.topic_id == topic_id
        )
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="이 주제는 이미 추가되어 있습니다.")
    
    new_topic_session = TopicSession(topic_id=topic_id, session_id=session_id)
    db.add(new_topic_session)
    await db.commit()
    return {"detail": "주제가 추가되었습니다."}
