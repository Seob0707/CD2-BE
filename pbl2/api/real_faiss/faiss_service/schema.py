from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Optional

class DocumentInput(BaseModel):
    page_content: str
    session_id: int
    user_id: int
    message_role: Literal["ai", "user", "feedback"] 
    # 피드백 관련 필드는 일단 주석 처리
    # target_message_id: Optional[str] = None
    # feedback_rating: Optional[Literal["like", "dislike"]] = None

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
        orm_mode = True 

class ConversationHistoryResponse(BaseModel):
    session_id: int
    user_id: int
    messages: List[ChatMessageOutput]
    total_messages: int

class SessionSearchQuery(BaseModel):
    session_id: int
    user_id: int
    query: str
    k: int = Field(5)

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

Query = SessionSearchQuery
