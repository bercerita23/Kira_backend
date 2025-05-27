from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from app.model.school_model import School
from app.model.reward_model import Reward
from app.model.user_history_model import UserHistory
from datetime import datetime
class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="stu")
    school_id = Column(Integer, ForeignKey("school.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime)

    school = relationship("School", back_populates="users")
    rewards = relationship("Reward", back_populates="user")
    histories = relationship("UserHistory", back_populates="user")
        
