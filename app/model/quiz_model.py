from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from app.model.question_model import Question


class Quiz(Base):
    __tablename__ = "quiz"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    questions = relationship("Question", back_populates="quiz")
    histories = relationship("UserHistory", back_populates="quiz")
