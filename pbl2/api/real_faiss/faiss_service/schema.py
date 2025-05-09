from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal

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

class SessionSearchQuery(BaseModel):
    session_id: int = Field(..., description="대화 세션 ID")
    user_id:    int = Field(..., description="요청자 유저 ID")
    query:      str = Field(..., description="검색할 텍스트")
    k:          int = Field(5, description="반환할 최대 결과 개수")

    class Config:
        schema_extra = {
            "example": {
                "session_id": 123,
                "user_id": 456,
                "query": "오늘 대화 요약해줘",
                "k": 5
            }
        }

class DocumentOutput(BaseModel):
    doc_id: str
    page_content: str
    metadata: Dict[str, Any]

class HistoryResponse(BaseModel):
    history: List[DocumentOutput]

class SessionSearchResult(BaseModel):
    doc_id: str
    page_content: str
    metadata: Dict[str, Any]
    score: float


Query = SessionSearchQuery