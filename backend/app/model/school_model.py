from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base




class School(Base):
    __tablename__ = "school"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    users = relationship("User", back_populates="school")
