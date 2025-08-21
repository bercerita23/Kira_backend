from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from app.config import Settings, settings

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession


def build_sqlalchemy_database_url_from_settings(_settings: Settings) -> str:
    """
    Builds a SQLAlchemy URL based on the provided settings.

    Parameters:
        _settings (Settings): An instance of the Settings class
        containing the PostgreSQL connection details.

    Returns:
        str: The generated SQLAlchemy URL.
    """
    return (
        f"postgresql+psycopg://{_settings.POSTGRES_USER}:{_settings.POSTGRES_PASSWORD}"
        f"@{_settings.POSTGRES_HOST}:{_settings.POSTGRES_PORT}/{_settings.POSTGRES_DB}"
    )


def get_engine(database_url: str, echo=False) -> Engine:
    """
    Creates and returns a SQLAlchemy Engine object for connecting to a database.

    Parameters:
        database_url (str): The URL of the database to connect to.
        Defaults to SQLALCHEMY_DATABASE_URL.
        echo (bool): Whether or not to enable echoing of SQL statements.
        Defaults to False.

    Returns:
        Engine: A SQLAlchemy Engine object representing the database connection.
    """
    engine = create_engine(database_url, echo=echo)
    return engine


def get_local_session(database_url: str, echo=False, **kwargs) -> sessionmaker:
    """
    Create and return a sessionmaker object for a local database session.

    Parameters:
        database_url (str): The URL of the local database.
        Defaults to `SQLALCHEMY_DATABASE_URL`.
        echo (bool): Whether to echo SQL statements to the console.
        Defaults to `False`.

    Returns:
        sessionmaker: A sessionmaker object configured for the local database session.
    """
    engine = get_engine(database_url, echo)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session

def get_async_session(database_url: str, echo=False) -> sessionmaker:
    """
    Returns an async sessionmaker for async DB operations.
    """
    engine = create_async_engine(
        database_url.replace("postgresql+psycopg", "postgresql+asyncpg"),  # use async driver
        echo=echo,
        pool_size=3,           # reduced pool size since we have 3 background tasks
        max_overflow=5,        # reduced max overflow
        pool_timeout=30,
        pool_recycle=300,     # recycle connections every 5 minutes
        pool_pre_ping=True    # verify connection is valid before using it
    )
    async_session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    return async_session

SQLALCHEMY_DATABASE_URL = build_sqlalchemy_database_url_from_settings(settings)