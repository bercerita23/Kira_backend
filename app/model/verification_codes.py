from sqlalchemy import Column, String, DateTime
from app.database.base_class import Base
from datetime import datetime

class VerificationCodes(Base):
    __tablename__ = "verification_code"
    
    email = Column(String(255), primary_key=True, index=True)
    code = Column(String(8), nullable=False)
    expires_at = Column(DateTime, nullable=False)