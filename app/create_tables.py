# create_tables.py
from sqlalchemy import create_engine
from app import model  # make sure all models are loaded
from app.model import user_model, question_model, quiz_model, reward_model, school_model, user_history_model
from sqlalchemy.ext.declarative import declarative_base
from app.database.base_class import Base

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:test@localhost:5432/test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

Base.metadata.create_all(bind=engine)
print("✅ Tables created.")