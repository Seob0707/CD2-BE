from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Literal, Optional

class DocumentInput(BaseModel):
    page_content: str
    session_id: int
    user_id: int
    message_role: Literal["user", "optimize", "report", "hitl_user", "hitl_ai"]
    target_message_id: Optional[str] = None

class AddResponse(BaseModel):
    added_ids: List[str]
    message: str

class HistoryRequest(BaseModel):
    session_id: int
    user_id: int

class ChatMessageOutput(BaseModel):
    message_id: str = Field(alias="doc_id")
    content: str = Field(alias="page_content")
    role: Literal["user", "optimize", "report", "hitl_user", "hitl_ai"]
    timestamp: str
    user_id: int

    model_config = ConfigDict(
        populate_by_name=True, 
        from_attributes=True    
    )

class ConversationHistoryResponse(BaseModel):
    session_id: int
    user_id: int
    title: Optional[str] = None
    topics: Optional[List[str]] = None
    messages: List[ChatMessageOutput]
    total_messages: int

    model_config = ConfigDict(
        from_attributes=True
    )

class SessionSearchQuery(BaseModel):
    session_id: int
    user_id: int
    query: str
    k: int = Field(5, gt=0)

    model_config = ConfigDict(
        json_schema_extra={ 
            "example": {
                "session_id": 123,
                "user_id": 456,
                "query": "오늘 대화 요약해줘",
                "k": 5
            }
        }
    )

class SessionSearchResult(BaseModel):
    doc_id: str
    page_content: str
    metadata: Dict[str, Any]
    score: float

class KeywordSearchRequest(BaseModel):
    keyword: str = Field(min_length=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "keyword": "오늘 날씨"
            }
        }
    )

Query = SessionSearchQuery
