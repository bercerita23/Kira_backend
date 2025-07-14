from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.base_class import Base
from datetime import datetime
from app.model.schools import School
from app.model.streaks import Streak
from app.model.user_badges import UserBadge
from app.model.points import Points
from app.model.quizzes import Quiz
from app.model.attempts import Attempt

class User(Base):
    __tablename__ = "users"
     
    user_id = Column(String(12), primary_key=True, index=True)
    school_id = Column(String(8), ForeignKey("schools.school_id"))
    email = Column(String(255), nullable=True, unique=True )
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now())
    notes = Column(String(512), nullable=True)
    last_login_time = Column(DateTime, nullable=True)
    is_super_admin = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    username = Column(String(50), nullable=True, unique=True)
    deactivated = Column(Boolean, default=False)
    
    school = relationship("School", back_populates="users")
    streak = relationship("Streak", back_populates="user", uselist=False)
    badges = relationship("UserBadge", back_populates="user", cascade="all, delete-orphan")
    points = relationship("Points", back_populates="user", uselist=False, cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="creator", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="user")