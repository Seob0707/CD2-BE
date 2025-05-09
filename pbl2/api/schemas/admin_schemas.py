from pydantic import BaseModel
from typing import List

class TopicCreate(BaseModel):
    topic_name: str

class TopicResponse(BaseModel):
    topic_id:   int
    topic_name: str

class LanguageCreate(BaseModel):
    lang_code: str

class LanguageResponse(BaseModel):
    lang_id:   int
    lang_code: str

class StatsItem(BaseModel):
    hour:  int
    count: int

class StatsResponse(BaseModel):
    stats: List[StatsItem]