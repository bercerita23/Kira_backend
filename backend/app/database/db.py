from typing import Generator

from app.database.session import SQLALCHEMY_DATABASE_URL, get_local_session
# from app.exceptions import SQLAlchemyException

from app.log import get_logger

log = get_logger(__name__)


def get_db() -> Generator:  # pragma: no cover
    """
    Returns a generator that yields a database session

    Yields:
        Session: A database session object.

    Raises:
        Exception: If an error occurs while getting the database session.
    """

    log.debug("getting database session")
    db = get_local_session(SQLALCHEMY_DATABASE_URL, False)()
    try:
        yield db
    finally:  # pragma: no cover
        log.debug("closing database session")
        db.close()  # pragma: no cover