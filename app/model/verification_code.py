from sqlalchemy import Column, String
from app.database.base_class import Base

class User(Base):
    __tablename__ = "verification_codes"
    email = Column(String, primary_key=True, index=True, nullable=False, unique=True)
    code = Column(String, nullable=False)