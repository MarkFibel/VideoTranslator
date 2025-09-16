from fastapi import APIRouter

from .routers import file_router, frontend_router, sse_router


def get_apps_router():
    router = APIRouter()
    router.include_router(frontend_router.router)
    router.include_router(file_router.router)
    router.include_router(sse_router.router)
    return router