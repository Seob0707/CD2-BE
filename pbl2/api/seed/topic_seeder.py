# api/seed/topic_seeder.py
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ORM import Topic
from fastapi import HTTPException

# 주제 이름을 입력받아 삽입하는 함수
async def insert_topic(topic_name: str, db: AsyncSession):
    if not topic_name:
        raise HTTPException(status_code=400, detail="주제 이름이 필요합니다.")

    new_topic = Topic(topic_name=topic_name)
    db.add(new_topic)
    await db.commit()
    await db.refresh(new_topic)

    return new_topic
