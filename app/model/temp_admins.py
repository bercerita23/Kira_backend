from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base_class import Base

class TempAdmin(Base):
    __tablename__ = "temp_admins"
    
    user_id = Column(String(12), primary_key=True, index=True)
    school_id = Column(String(8), ForeignKey("schools.school_id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now())
    
    school = relationship("School")