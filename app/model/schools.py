from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class School(Base): 
    __tablename__ = "schools"

    school_id = Column(String(8), primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True) #shang-chen.hsieh@sjsu.edu
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    telephone = Column(String(20), nullable=True)

    users = relationship("User", back_populates="school")
    quizzes = relationship("Quiz", back_populates="school") 