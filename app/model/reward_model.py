from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base_class import Base


class Reward(Base):
    __tablename__ = "reward"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    type = Column(String, nullable=False)
    value = Column(Integer)
    awarded_at = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    user = relationship("User", back_populates="rewards")
