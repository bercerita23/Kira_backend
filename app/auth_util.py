from datetime import datetime, timedelta
from typing import Any, Union

from jose import jwt

from passlib.context import CryptContext
from app.model.users import User
from app.config import settings
from app.database.db import get_db
import random
from sqlalchemy.orm import Session
from fastapi import Depends


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any], email: str, first_name: str, role: str, school_id: str, expires_delta: timedelta = None
) -> str:
    """
    Creates an access token.

    Parameters:
        subject (Union[str, Any]): The subject for which the access token is created.
        expires_delta (timedelta, optional): The expiration time for the access token. Defaults to None.

    Returns:
        str: The encoded access token.
    """
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "email": email, "first_name": first_name, "role": role, "school_id": school_id, "subject": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify if a plain password matches a hashed password.

    Parameters:
        plain_password (str): The plain password to be verified.
        hashed_password (str): The hashed password to compare with.

    Returns:
        bool: True if the plain password matches the hashed password, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate the hash value of a password.

    Parameters:
        password (str): The password to be hashed.

    Returns:
        str: The hash value of the password.
    """
    return pwd_context.hash(password)

def generate_unique_user_id(db: Session = Depends(get_db)) -> str:
    while True:
        candidate = str(random.randint(10**11, 10**12 - 1))  # Generates a 12-digit number
        if not db.query(User).filter_by(user_id=candidate).first():
            return candidate