from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Optional

class DocumentInput(BaseModel):
    page_content: str
    session_id: int
    user_id: int
    message_role: Literal["ai", "user", "feedback"]

class AddResponse(BaseModel):
    added_ids: List[str]
    message: str

class HistoryRequest(BaseModel):
    session_id: int
    user_id: int

class ChatMessageOutput(BaseModel):
    message_id: str = Field(alias="doc_id")
    content: str = Field(alias="page_content")
    role: Literal["ai", "user", "feedback"]
    timestamp: str
    user_id: int

    class Config:
        allow_population_by_field_name = True
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    session_id: int
    user_id: int
    title: Optional[str] = None
    topics: Optional[List[str]] = None
    messages: List[ChatMessageOutput]
    total_messages: int

    class Config:
        from_attributes = True

class SessionSearchQuery(BaseModel):
    session_id: int
    user_id: int
    query: str
    k: int = Field(5, gt=0)

    class Config:
        schema_extra = {
            "example": {
                "session_id": 123,
                "user_id": 456,
                "query": "오늘 대화 요약해줘",
                "k": 5
            }
        }

class SessionSearchResult(BaseModel):
    doc_id: str
    page_content: str
    metadata: Dict[str, Any]
    score: float

class KeywordSearchRequest(BaseModel):
    keyword: str = Field(min_length=1)

    class Config:
        schema_extra = {
            "example": {
                "keyword": "오늘 날씨"
            }
        }

Query = SessionSearchQuery