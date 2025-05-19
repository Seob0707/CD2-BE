from pydantic import BaseModel, ConfigDict 
from typing import Optional

class LanguageBase(BaseModel):
    lang_code: Optional[str] = None

class LanguageResponse(LanguageBase):
    lang_id: int
    model_config = ConfigDict(from_attributes=True)