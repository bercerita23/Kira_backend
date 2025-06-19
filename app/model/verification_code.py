from sqlalchemy import Column, String, DateTime
from app.database.base_class import Base

class VerificationCode(Base):
    __tablename__ = "verification_codes"
    email = Column(String, primary_key=True, index=True, nullable=False, unique=True)
    code = Column(String, nullable=False)
    expired_at = Column(DateTime, nullable=False)