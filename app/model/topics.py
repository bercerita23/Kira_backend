from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, ARRAY, Text
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class Topic(Base): 
    __tablename__ = "topics"

    topic_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_name = Column(String(255), nullable=False)
    s3_bucket_url = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.now)
    state = Column(String(50), nullable=False, default="READY_FOR_GENERATION")
    hash_value = Column(String(512), nullable=False)
    week_number = Column(Integer, nullable=False) 
    school_id = Column(String(8), ForeignKey("schools.school_id"), nullable=False)
    summary = Column(Text, nullable=False, default="")

    school = relationship("School", back_populates="topics")
    questions = relationship("Question", back_populates="topic")
    # chat_sessions = relationship("ChatSession", back_populates="topic")
