from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database import Base

class File(Base):
    __tablename__ = "file"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('session.session_id'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(255), nullable=False)  
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


    session = relationship("Session", back_populates="files")
