from fastapi import FastAPI
from typing import Union
from app.router import (
    auth_router, 
)
from app.config import settings, Settings


# start the FastAPI application with 
# fastapi dev main.py
app = FastAPI(title="Kira", version="0.0.1") 

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

#####################
### test endpoint ###
#####################
@app.get("/")
def read_root():
    return {"Hello From: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': '01'}
