from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, Float
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class Attempt(Base): 
    __tablename__ = "attempts"

    attempt_id = Column(Integer, index=True, primary_key=True, autoincrement=True)

    # FK
    user_id = Column(String(12), ForeignKey("users.user_id", ondelete="CASCADE"))
    quiz_id = Column(Integer, ForeignKey("quizzes.quiz_id", ondelete="CASCADE"))

    # attributes 
    score = Column(Float, nullable=False)
    attempt_number = Column(Integer, nullable=False) 
    attempted_at = Column(DateTime, nullable=False)

    # relationship 
    user = relationship("User", back_populates="attempts")
    quiz = relationship("Quiz", back_populates="attempts")

