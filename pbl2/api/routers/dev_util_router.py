from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.seed.topic_seeder import insert_topic  # 수정된 함수 import

router = APIRouter()

# Pydantic 모델 정의 (사용자 입력 값 받기)
class TopicCreateInput(BaseModel):
    topic_name: str

# 주제 이름을 JSON으로 입력받아 삽입하는 API
@router.post("/seed/topics")
async def seed_topic(
    topic_data: TopicCreateInput,  # JSON Body를 통해 입력 받음
    db: AsyncSession = Depends(get_db)
):
    new_topic = await insert_topic(topic_data.topic_name, db)  # 주제 삽입 함수 호출
    return {"message": f"주제 '{new_topic.topic_name}'가 성공적으로 추가되었습니다."}
