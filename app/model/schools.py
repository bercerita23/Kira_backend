from sqlalchemy import Column, String, Enum as SAEnum, text
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from enum import Enum as PyEnum

class SchoolStatus(PyEnum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class School(Base): 
    __tablename__ = "schools"
    #test
    school_id = Column(String(8), primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True) #shang-chen.hsieh@sjsu.edu
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    telephone = Column(String(20), nullable=True)
    status = Column(
        SAEnum(
            SchoolStatus,
            name="school_status",     # the Postgres enum type name
            native_enum=True,         # use real PG ENUM instead of CHECK
            validate_strings=True,    # guard against bad strings
        ),
        nullable=False,
        server_default=text("'active'::school_status"),
    )

    users = relationship("User", back_populates="school")
    quizzes = relationship("Quiz", back_populates="school") 
    questions = relationship("Question", back_populates="school")
    
    topics = relationship("Topic", back_populates="school")