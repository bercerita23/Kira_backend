from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class Analytics(Base): 
    __tablename__ = "analytics"
    
    #PK
    #FK
    user_id = Column(String(12), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True, index=True)
    
    # attributes
    engagement_time_ms = Column(Integer, default=0, nullable=False) 
    created_at = Column(DateTime, default=datetime.now)
    # relationship
    user = relationship("User", back_populates="analytics") 

