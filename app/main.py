from fastapi import FastAPI
from typing import Union

from app.router import (
    auth_router, 
    users_router
)
from app.config import settings


# start the FastAPI application with 
# fastapi dev main.py
app = FastAPI(title=settings.PROJECT_NAME, version=settings.API_VERSION) 

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/users", tags=["User"])
#####################
### test endpoint ###
#####################
@app.get("/")
def read_root():
    return {"KIRA: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': settings.API_VERSION}
