from pydantic import BaseModel

class TopicBase(BaseModel):
    topic_name: str

class TopicCreate(TopicBase):
    pass

class TopicUpdate(TopicBase):
    pass

class TopicOut(TopicBase):
    topic_id: int

    class Config:
        from_attributes = True

TopicSearchOut = TopicOut
