from fastapi import FastAPI
# from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.model import users, schools, streaks, badges, user_badges, points, quizzes, questions, attempts, temp_admins, verification_codes, topics, reference_counts, chats 
# from app.repeated_tasks.ready import *
# from app.repeated_tasks.question_and_prompt import * 
# from app.repeated_tasks.visuals import *
# import asyncio
# import logging
# from typing import Callable, Dict
from app.router import (
    auth_router, 
    users_router, 
    super_admin_router, 
    admin_router,
)
from app.config import settings

# task_locks: Dict[str, asyncio.Lock] = {
#     "prompt_generation": asyncio.Lock(),
#     "ready_for_review": asyncio.Lock(),
#     "visual_generation": asyncio.Lock(),
# }
# async def run_task(name: str, func: Callable, interval: int = 30):
#     """
#     Run a background task periodically, ensuring only one instance
#     of this task is running at a time.
#     """
#     consecutive_errors = 0
#     max_backoff = 300  # 5 minutes

#     while True:
#         lock = task_locks[name]
#         if lock.locked():
#             # Another instance is running, wait for next interval
#             await asyncio.sleep(interval)
#             continue

#         try:
#             async with lock:
#                 try:
#                     await func()
#                     consecutive_errors = 0  # Reset on success
#                 except Exception as e:
#                     consecutive_errors += 1
#                     error_msg = str(e)
#                     print(f"Error in {name}: {error_msg}")
                    
#                     # Exponential backoff on connection errors
#                     if "remaining connection slots are reserved" in error_msg:
#                         backoff = min(interval * (2 ** consecutive_errors), max_backoff)
#                         print(f"{name}: Connection pool exhausted, backing off for {backoff}s")
#                         await asyncio.sleep(backoff)
#                         continue

#             # Normal interval between runs
#             await asyncio.sleep(interval)

#         except Exception as outer_e:
#             print(f"Critical error in task runner for {name}: {outer_e}")
#             await asyncio.sleep(interval)

# background_tasks = set()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger = logging.getLogger("uvicorn")
#     logger.info("Starting background tasks...")

#     # Start wrapped background tasks (with concurrency control)
#     prompt_task = asyncio.create_task(run_task("prompt_generation", prompt_generation, 30))
#     ready_task = asyncio.create_task(run_task("ready_for_review", ready_for_review, 30))
#     visual_task = asyncio.create_task(run_task("visual_generation", visual_generation, 30))

#     logger.info("Background tasks created: prompt_generation, ready_for_review, visual_generation")

#     # Track tasks
#     background_tasks.update([prompt_task, ready_task, visual_task])

#     # Auto cleanup
#     for task in [prompt_task, ready_task, visual_task]:
#         task.add_done_callback(background_tasks.discard)

#     yield

#     # Cancel all background tasks
#     for task in background_tasks:
#         task.cancel()

#     if background_tasks:
#         await asyncio.gather(*background_tasks, return_exceptions=True)


app = FastAPI(
    # lifespan=lifespan,  # COMMENTED - Worker handles background tasks now
    title=settings.PROJECT_NAME, 
    version=settings.API_VERSION
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://www.kiraclassroom.com",
        "https://kiraclassroom.com",
        "https://main.d3hzyon2wqrdca.amplifyapp.com",
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
