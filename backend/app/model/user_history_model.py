from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from app.model.quiz_model import Quiz

class UserHistory(Base):
    __tablename__ = "user_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    quiz_id = Column(Integer, ForeignKey("quiz.id"))
    score = Column(Integer)
    attempt_date = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    user = relationship("User", back_populates="histories")
    quiz = relationship("Quiz", back_populates="histories")
