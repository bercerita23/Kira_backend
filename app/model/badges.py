from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime


class Badge(Base):
    __tablename__ = "badges"

    badge_id = Column(String(8), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(512), nullable=True)
    icon_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Relationship to UserBadge
    users = relationship("UserBadge", back_populates="badge", cascade="all, delete-orphan")
