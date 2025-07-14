from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime
from app.model.schools import School
from app.model.attempts import Attempt
from app.model.questions import Question

class Quiz(Base): 
    __tablename__ = "quizzes"

    quiz_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # FK
    school_id = Column(String(8), ForeignKey("schools.school_id"), nullable=False)
    creator_id = Column(String(12), ForeignKey("users.user_id"), nullable=False)

    # attributes
    name = Column(String(255), nullable=False)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # relationship
    school = relationship("School", back_populates="quizzes")
    attempts = relationship("Attempt", back_populates="quiz", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="quizzes")
    