from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from typing import List

class TopicInfo(BaseModel):
    topic_id: int
    topic_name: str

    class Config:
        from_attributes = True

class SessionCreate(BaseModel):
    title: Optional[str] = None
    topic_id: Optional[int] = None  

class SessionUpdate(BaseModel):
    title: Optional[str] = None

class SessionOut(BaseModel):
    session_id: int
    user_id: int
    title: str
    topics: List[TopicInfo]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionTopicAdd(BaseModel):
    topic_id: int
