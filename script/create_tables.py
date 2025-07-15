# create_tables.py
from sqlalchemy import create_engine
from app.model import attempts, badges, questions, points, quizzes, schools, streaks, temp_admins, user_badges, users, verification_codes, attempts, points, questions, quizzes
from sqlalchemy.ext.declarative import declarative_base
from app.database.base_class import Base
from app.config import settings

from sqlalchemy import inspect



SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

Base.metadata.create_all(bind=engine)
print("✅ Tables created.")

inspector = inspect(engine)
print("📋 Existing tables:", inspector.get_table_names())