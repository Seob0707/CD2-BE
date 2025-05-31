from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Literal, Optional

class DocumentInput(BaseModel):
    page_content: str
    session_id: int
    user_id: int
    message_role: Literal["user", "optimize", "report", "hitl_user", "hitl_ai"]
    target_message_id: Optional[str] = None
    evaluation_indices: Optional[List[int]] = Field(None, description="AI가 평가한 항목 인덱스 리스트 (1~30)")
    recommendation_status: Optional[Literal["like", "dislike"]] = Field(None, description="추천(like), 비추천(dislike), 또는 미설정(null) 상태")

class AddResponse(BaseModel):
    added_ids: List[str]
    message: str

class HistoryRequest(BaseModel):
    session_id: int
    user_id: int

class ChatMessageOutput(BaseModel):
    message_id: str
    content: str = Field(alias="page_content")
    role: Literal["user", "optimize", "report", "hitl_user", "hitl_ai"]
    timestamp: str
    user_id: int
    evaluation_indices: Optional[List[int]] = Field(None, description="저장된 평가 항목 인덱스 리스트")
    recommendation_status: Optional[Literal["like", "dislike"]] = Field(None, description="저장된 추천/비추천 상태")

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
    message_id: str
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

class MessageUpdateRequest(BaseModel):
    message_id: str = Field(description="수정할 메시지의 고유 ID")
    new_page_content: str = Field(description="새로운 메시지 내용")

class MessageUpdateResponse(BaseModel):
    message_id: str
    message: str

class MessageDeleteResponse(BaseModel):
    message_id: str
    message: str


Query = SessionSearchQuery