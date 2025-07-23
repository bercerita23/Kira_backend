from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, PrimaryKeyConstraint, Integer
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime


class UserBadge(Base):
    __tablename__ = "user_badges"

    user_id = Column(String(12), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    badge_id = Column(String(8), ForeignKey("badges.badge_id", ondelete="CASCADE"), nullable=False)
    earned_at = Column(DateTime, default=datetime.now, nullable=False)
    view_count = Column(Integer, default=0)

    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'badge_id'),
    )
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge", back_populates="users")
