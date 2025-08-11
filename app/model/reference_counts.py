from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, ARRAY
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class ReferenceCount(Base): 
    __tablename__ = "reference_counts"
    
    hash_value = Column(String(512), primary_key=True, nullable=False, unique=True)
    referred_s3_url = Column(String(255), nullable=False)
    count = Column(Integer, default=1)