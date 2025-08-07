from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.model import users, schools, streaks, badges, user_badges, points, quizzes, questions, attempts, temp_admins, verification_codes, topics
from app.repeated_tasks import *
import asyncio


from app.router import (
    auth_router, 
    users_router, 
    super_admin_router, 
    admin_router,
)
from app.config import settings

background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting up application...")
    

    # Start the background task
    # hello_world_task = asyncio.create_task(hello_world())
    # hello_sky_task = asyncio.create_task(hello_sky())
    prompt_task = asyncio.create_task(prompt_generation())

    # Add tasks to the set for tracking
    # background_tasks.add(hello_world_task)
    # background_tasks.add(hello_sky_task)
    background_tasks.add(prompt_task)

    # auto cleanup for taskss
    # hello_world_task.add_done_callback(background_tasks.discard)
    # hello_sky_task.add_done_callback(background_tasks.discard) 
    prompt_task.add_done_callback(background_tasks.discard) 

    yield
    
    # Shutdown logic
    print("Shutting down application...")
    
    # Cancel all background tasks
    for task in background_tasks:
        task.cancel()
    
    # Wait for all tasks to complete cancellation
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan, 
              title=settings.PROJECT_NAME, 
              version=settings.API_VERSION) 

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://www.kiraclassroom.com",
        "https://kiraclassroom.com",
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

#####################
### Root Endpoint ###
#####################
@app.get("/")
def read_root():
    return {"KIRA: ": settings.PROJECT_NAME, 'Environment: ': settings.ENV, 'Version: ': settings.API_VERSION, 'Docs: ': "https://api.kiraclassroom.com/docs"}
