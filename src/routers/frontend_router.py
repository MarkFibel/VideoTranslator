from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["frontend"])


@router.get("/")
async def get_index():
    """Обслуживание главной страницы"""
    return FileResponse("public/index.html")