from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Quiz(Base):
    __tablename__ = "quiz"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    questions = relationship("Question", back_populates="quiz")
    histories = relationship("UserHistory", back_populates="quiz")
