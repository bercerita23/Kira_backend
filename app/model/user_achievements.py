from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime

class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id = Column(String(12), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    achievement_id = Column(String(8), ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime, default=datetime.now, nullable=False)
    is_viewed = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'achievement_id'),
    )

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="users")