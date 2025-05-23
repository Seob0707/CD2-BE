from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, text, update
from fastapi import HTTPException, status

from api.models.ORM import Topic, Language, Session, Setting

RESERVED_LANG_ID_FOR_AUTO = 1


async def create_topic(db: AsyncSession, name: str) -> Topic:
    existing = await db.execute(select(Topic).where(Topic.topic_name == name))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 존재하는 토픽입니다.")
    topic = Topic(topic_name=name)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def delete_topic(db: AsyncSession, topic_id: int) -> None:
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="토픽을 찾을 수 없습니다.")
    await db.delete(topic)
    await db.commit()


async def create_language(db: AsyncSession, code: str) -> Language:
    existing = await db.execute(select(Language).where(Language.lang_code == code.lower()))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 존재하는 언어 코드입니다.")
    
    new_lang = Language(lang_code=code.lower())
    db.add(new_lang)
    await db.commit() 
    await db.refresh(new_lang)

    if new_lang.lang_id == RESERVED_LANG_ID_FOR_AUTO:
        await db.delete(new_lang)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"언어 코드 '{code}'가 예약된 ID ({RESERVED_LANG_ID_FOR_AUTO})로 생성되었습니다. "
                   f"이 ID는 '자동 선택' 기능에 사용됩니다. "
                   f"데이터베이스에서 language 테이블의 AUTO_INCREMENT 시작 값을 {RESERVED_LANG_ID_FOR_AUTO + 1}로 설정하거나, "
                   f"초기 언어 데이터(lang_id={RESERVED_LANG_ID_FOR_AUTO + 1}부터 시작)를 먼저 추가하십시오."
        )
    return new_lang


async def delete_language(db: AsyncSession, language_id: int) -> None:
    if language_id == RESERVED_LANG_ID_FOR_AUTO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language ID {RESERVED_LANG_ID_FOR_AUTO}는 '자동 선택' 기능을 위해 시스템에서 사용되므로 삭제할 수 없습니다."
        )
    
    lang_to_delete = await db.get(Language, language_id)
    if not lang_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 언어를 찾을 수 없습니다.")
    
    update_stmt = (
        update(Setting)
        .where(Setting.language == language_id)
        .values(language=RESERVED_LANG_ID_FOR_AUTO)
    )
    await db.execute(update_stmt)
    
    await db.delete(lang_to_delete)
    await db.commit()


async def get_visit_stats(db: AsyncSession) -> list[dict]:
    stmt = (
        select(
            extract('hour', Session.created_at).label('hour'),
            func.count(Session.session_id).label('count')
        )
        .where(Session.created_at >= text("NOW() - INTERVAL '1 DAY'"))
        .group_by(extract('hour', Session.created_at))
        .order_by(extract('hour', Session.created_at))
    )
    result = await db.execute(stmt)
    return [{"hour": r.hour, "count": r.count} for r in result]