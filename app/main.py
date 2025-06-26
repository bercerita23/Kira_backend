from fastapi import FastAPI
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

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/users", tags=["User"])
app.include_router(super_admin_router, prefix="/super_admin", tags=["Super Admin"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(school_router, prefix="/school", tags=["School"])    

#####################
### test endpoint ###
#####################
@app.get("/")
def read_root():
    return {"KIRA: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': settings.API_VERSION}
