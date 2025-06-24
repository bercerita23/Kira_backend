from fastapi import FastAPI
from typing import Union

from app.router import (
    auth_router, 
)
from app.config import settings, Settings
import asyncio
from app.background_task import cleanup_verification_codes
from contextlib import asynccontextmanager


# start the FastAPI application with 
# fastapi dev main.py
app = FastAPI(title="Kira", version="0.0.1") 

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup code here
#     cleanup_task = asyncio.create_task(cleanup_verification_codes())
#     try:
#         yield
#     finally:
#         # Shutdown code here - cancel cleanup task gracefully
#         cleanup_task.cancel()
#         try:
#             await cleanup_task
#         except asyncio.CancelledError:
#             pass
# 
# app.router.lifespan_context = lifespan

#####################
### test endpoint ###
#####################
@app.get("/")
def read_root():
    return {"Hello From: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': '01'}
