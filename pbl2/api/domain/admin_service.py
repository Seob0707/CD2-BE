from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, text
from fastapi import HTTPException, status

from api.models.ORM import Topic, Language, Session  

async def create_topic(db: AsyncSession, name: str) -> Topic:
    existing = await db.execute(select(Topic).where(Topic.topic_name == name))
    if existing.scalars().first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="이미 존재하는 토픽입니다.")
    topic = Topic(topic_name=name)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic

async def delete_topic(db: AsyncSession, topic_id: int) -> None:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="토픽을 찾을 수 없습니다.")
    await db.delete(topic)
    await db.commit()


async def create_language(db: AsyncSession, code: str) -> Language:
    existing = await db.execute(select(Language).where(Language.lang_code == code))
    if existing.scalars().first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="이미 존재하는 언어 코드입니다.")
    lang = Language(lang_code=code)
    db.add(lang)
    await db.commit()
    await db.refresh(lang)
    return lang

async def delete_language(db: AsyncSession, language_id: int) -> None:
    lang = await db.get(Language, language_id)
    if not lang:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="언어를 찾을 수 없습니다.")
    await db.delete(lang)
    await db.commit()


async def get_visit_stats(db: AsyncSession) -> list[dict]:
    """
    지난 24시간 동안 세션 생성 시점을 시간대별로 집계
    """
    stmt = (
        select(
            extract('hour', Session.created_at).label('hour'),
            func.count(Session.session_id).label('count')
        )
        .where(Session.created_at >= text("NOW() - INTERVAL 1 DAY"))
        .group_by('hour')
        .order_by('hour')
    )
    result = await db.execute(stmt)
    return [{"hour": r.hour, "count": r.count} for r in result]

