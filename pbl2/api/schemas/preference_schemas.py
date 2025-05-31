from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, List

class PreferenceInput(BaseModel):
    message_id: str 
    session_id: int
    rating: Literal["like", "dislike"]
    preference_text: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_id": "faiss_doc_id_2",
                "session_id": 101,
                "rating": "like",
                "preference_text": "매우 유용합니다!"
            }
        }
    )

class PreferenceSubmitResponse(BaseModel):
    message: str
    processed_preference_id: Optional[str] = None

class PreferenceFileReceiveResponse(BaseModel):
    message: str
    file_path: str

class PreferenceFileSendRequest(BaseModel):
    session_id: str

class PreferenceFileInfo(BaseModel):
    filename: str
    content_type: Optional[str] = None
    message: str