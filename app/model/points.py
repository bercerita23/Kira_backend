from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime



class Points(Base): 
    __tablename__ = "points"
    
    #PK
    #FK
    user_id = Column(String(12), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True, index=True)
    
    # attributes
    points = Column(Integer, default=0, nullable=False) 
    # relationship
    user = relationship("User", back_populates="points") 

