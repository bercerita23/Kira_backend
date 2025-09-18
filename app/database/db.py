from typing import Generator, AsyncGenerator
from contextlib import contextmanager
from app.database.session import SQLALCHEMY_DATABASE_URL, get_local_session, get_async_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
# from app.exceptions import SQLAlchemyException

from app.log import get_logger

log = get_logger(__name__)


ENGINE = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,          # max number of persistent connections in the pool
    max_overflow=0,       # 0 means never open more than pool_size
    pool_timeout=30,      # seconds to wait for a connection before raising
    pool_recycle=1800,    # recycle connections periodically (helps stale conns)
    pool_pre_ping=True,   # validates connections before using
    future=True,
)
SessionLocal = sessionmaker(
    bind=ENGINE,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)
def get_db() -> Generator:  # pragma: no cover
    """
    Returns a generator that yields a database session

    Yields:
        Session: A database session object.

    Raises:
        Exception: If an error occurs while getting the database session.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async_session_maker = get_async_session(SQLALCHEMY_DATABASE_URL, False)
    session = None
    try:
        session = async_session_maker()
        yield session
    except Exception as e:
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            try:
                await session.close()
            except Exception as e:
                log.error(f"Error closing session: {e}")
            finally:
                session = None


@contextmanager
def get_ctx_db(database_url: str) -> Generator:
    """
    Context manager that creates a database session and yields
    it for use in a 'with' statement.

    Parameters:
        database_url (str): The URL of the database to connect to.

    Yields:
        Generator: A database session.

    Raises:
        Exception: If an error occurs while getting the database session.

    """
    db = get_local_session(database_url)()
    try:
        yield db
    except Exception as e:
        log.error("An error occurred while getting the database session. Error: %s", e)
        
    finally:
        db.close()