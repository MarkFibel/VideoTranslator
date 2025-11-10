import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.config.app_config import settings

router = APIRouter(tags=["frontend"])
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Обслуживание главной страницы с формой загрузки видео"""
    
    context = {
        "request": request,
        "captcha_sitekey": settings.CAPTCHA_SITEKEY
    }
    
    return request.app.state.templates.TemplateResponse("translator/index.html", context)
