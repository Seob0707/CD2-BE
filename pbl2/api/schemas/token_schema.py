from pydantic import BaseModel, Field
from typing import Optional

class TokenPayload(BaseModel):
    token: str

class TokenValidationResponse(BaseModel):
    is_valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    message: Optional[str] = None