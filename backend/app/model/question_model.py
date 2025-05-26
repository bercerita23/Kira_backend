from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base


class Question(Base):
    __tablename__ = "question"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quiz.id"))
    type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    choices = Column(String)
    correct_answer = Column(String, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    quiz = relationship("Quiz", back_populates="questions")
