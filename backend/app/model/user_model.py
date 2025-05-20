from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    school_id = Column(Integer, ForeignKey("school.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    school = relationship("School", back_populates="users")
    rewards = relationship("Reward", back_populates="user")
    histories = relationship("UserHistory", back_populates="user")
