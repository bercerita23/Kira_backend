from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base_class import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(12), ForeignKey("users.user_id"))
    # topic_id = Column(Integer, ForeignKey("topics.topic_id", ondelete="SET NULL"))
    # quiz_id = Column(Integer, ForeignKey("quiz.quiz_id"))
    turn_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    context_text = Column(Text, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User", back_populates="chat_sessions")
    # topic = relationship("Topic", back_populates="chat_sessions")
    
    def duration_minutes(self):
        """for calculating duration in minutes"""
        end_time = self.ended_at or datetime.now()
        return (end_time - self.created_at).total_seconds() // 60


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String(20))   # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    session = relationship("ChatSession", back_populates="messages")
    