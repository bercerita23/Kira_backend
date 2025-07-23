from sqlalchemy import Column, String, Integer, Text
from app.database.base_class import Base
from sqlalchemy.orm import relationship

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(String(6), primary_key=True, index=True)
    
    name_en = Column(String(100), nullable=True)  
    name_ind = Column(String(100), nullable=True)  
    
    description_en = Column(Text, nullable=True)    # English description
    description_ind = Column(Text, nullable=True)    # Indonesian description

    points = Column(Integer, nullable=False)         # e.g. 10, 50, etc.

    users = relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")