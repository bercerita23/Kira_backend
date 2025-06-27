from app.router.api.auth import router as auth_router
from app.router.api.users import router as users_router
from app.router.api.super_admin import router as super_admin_router
from app.router.api.admin import router as admin_router
from app.router.api.school import router as school_router
from app.router.api.code import router as code_router
__all__ = [
    "auth_router",
    "users_router",
    "super_admin_router", 
    "admin_router",
    "school_router",
    "code_router",
]