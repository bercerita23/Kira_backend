from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Union

from app.router import (
    auth_router, 
    users_router, 
    super_admin_router, 
    admin_router,
    school_router,
)
from app.config import settings


app = FastAPI(title=settings.PROJECT_NAME, version=settings.API_VERSION) 

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://www.kira.bercerita.org",
        "https://kira.bercerita.org",
        "http://localhost:3000",  # For local development
        "http://localhost:5173",  # For Vite development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/users", tags=["User"])
app.include_router(super_admin_router, prefix="/super_admin", tags=["Super Admin"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(school_router, prefix="/school", tags=["School"])   

#####################
### Root Endpoint ###
#####################
@app.get("/")
def read_root():
    return {"KIRA: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': settings.API_VERSION}
