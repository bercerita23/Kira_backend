# create_tables.py
from sqlalchemy import create_engine
from app import model  # make sure all models are loaded
from app.model import user_model, question_model, quiz_model, reward_model, school_model, user_history_model
from sqlalchemy.ext.declarative import declarative_base
from app.database.base_class import Base
from app.config import settings, settings

from sqlalchemy import inspect



SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

Base.metadata.create_all(bind=engine)
print("✅ Tables created.")

inspector = inspect(engine)
print("📋 Existing tables:", inspector.get_table_names())