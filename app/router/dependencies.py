from typing import Tuple, Union

from fastapi import Depends, Query, status, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.model.users import User
from app.schema.auth_schema import TokenPayload

oauth2_scheme_ada = OAuth2PasswordBearer(tokenUrl="auth/login-ada")
oauth2_scheme_stu = OAuth2PasswordBearer(tokenUrl="auth/login-stu")


def get_pagination_params(
    skip: int = Query(0, ge=0), limit: int = Query(10, gt=0)
) -> Tuple[int, int]:
    return skip, limit


def get_token_from_any_scheme(
    token_ada: Union[str, None] = Security(oauth2_scheme_ada),
    token_stu: Union[str, None] = Security(oauth2_scheme_stu),
) -> str:
    """
    Try to extract token from either ADA or STU login schemes.
    Raises 403 if no token is found.
    """
    if token_ada:
        return token_ada
    if token_stu:
        return token_stu
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")

def get_token(token: str = Depends(get_token_from_any_scheme)) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError) as e:
        print(f"Exception: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials") from e
    return token_data


def get_current_user(
    db: Session = Depends(get_db), token: TokenPayload = Depends(get_token)
) -> User:
    user = db.query(User).filter(User.user_id == token.sub).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user isn't an admin.",
        )
    return current_user


def get_current_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user isn't a super admin.",
        )
    return current_user
