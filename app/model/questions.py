from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime



class Question(Base): 
    __tablename__ = "questions"

    question_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # FK
    quiz_id = Column(Integer, ForeignKey("quizzes.quiz_id"))

    # attributes
    content = Column(String(255), nullable=False)
    question_type = Column(String(50), nullable=False)
    points = Column(Integer, nullable=False)
    answer = Column(String(50), nullable=False)

    # relationship 
    quiz = relationship("Quiz", back_populates="questions")
