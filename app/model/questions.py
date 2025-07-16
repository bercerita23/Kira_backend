from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, ARRAY
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime



class Question(Base): 
    __tablename__ = "questions"
    #test
    question_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    school_id = Column(String(8), ForeignKey("schools.school_id"), nullable=False)


    # attributes
    content = Column(String(255), nullable=False)
    options = Column(ARRAY(String(255)), nullable=False)
    question_type = Column(String(50), nullable=False)
    points = Column(Integer, nullable=False)
    answer = Column(String(255), nullable=False)
    image_url = Column(String(512), nullable=True)
    
    # relationship
    school = relationship("School", back_populates="questions")
    