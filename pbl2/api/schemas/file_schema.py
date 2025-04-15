from pydantic import BaseModel
from datetime import datetime

class FileOut(BaseModel):
    file_id: int
    session_id: int
    file_name: str
    file_url: str
    uploaded_at: datetime

    class Config:
       from_attributes = True
        