from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.database import get_db
from api.models.ORM import Topic
from api.schemas.topic_schema import TopicCreate, TopicUpdate, TopicOut, TopicSearchOut
from api.core.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=list[TopicOut])
async def list_topics(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    stmt = select(Topic)
    result = await db.execute(stmt)
    topics = result.scalars().all()
    return [TopicOut(**t.__dict__) for t in topics]

@router.post("/", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
async def create_topic(
    topic: TopicCreate,
    db: AsyncSession = Depends(get_db)
):
    new_topic = Topic(topic_name=topic.topic_name)
    db.add(new_topic)
    await db.commit()
    await db.refresh(new_topic)
    return TopicOut(**new_topic.__dict__)

@router.put("/{topic_id}", response_model=TopicOut)
async def update_topic(
    topic_id: int,
    topic_update: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = await db.execute(select(Topic).where(Topic.topic_id == topic_id))
    topic = result.scalars().first()

    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    topic.topic_name = topic_update.topic_name
    await db.commit()
    await db.refresh(topic)
    return TopicOut(**topic.__dict__)

@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = await db.execute(select(Topic).where(Topic.topic_id == topic_id))
    topic = result.scalars().first()

    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    await db.delete(topic)
    await db.commit()
    return {"detail": "Topic deleted successfully"}
