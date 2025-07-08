from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class Streak(Base):
    __tablename__ = "streaks"

    user_id = Column(String(12), ForeignKey("users.user_id"), primary_key=True, index=True)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_activity = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, nullable=False)

    user = relationship("User", back_populates="streak")
