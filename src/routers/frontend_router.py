import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["frontend"])
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def get_index():
    """Обслуживание главной страницы"""
    
    # Читаем HTML файл
    with open("public/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Создаем response с модифицированным HTML
    response = HTMLResponse(content=html_content)
    
    return response