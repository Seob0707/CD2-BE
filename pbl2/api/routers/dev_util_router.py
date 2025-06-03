from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.seed.topic_seeder import insert_topic 

router = APIRouter()

class TopicCreateInput(BaseModel):
    topic_name: str

@router.post("/seed/topics")
async def seed_topic(
    topic_data: TopicCreateInput,  
    db: AsyncSession = Depends(get_db)
):
    new_topic = await insert_topic(topic_data.topic_name, db)  
    return {"message": f"주제 '{new_topic.topic_name}'가 성공적으로 추가되었습니다."}
