from pydantic import BaseModel, Field
from typing import Literal, Optional

class PreferenceInput(BaseModel):
    target_message_id: str
    session_id: int
    rating: Literal["like", "dislike"] 
    preference_text: Optional[str] = None

class PreferenceResponse(BaseModel):
    message: str
    processed_preference_id: Optional[str] = None
    saved_file_path: Optional[str] = None
