import logging
import os
from fastapi import APIRouter, Request, HTTPException
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


@router.get("/test-sse", response_class=HTMLResponse)
async def get_sse_test():
    """Тестовая страница для проверки SSE upload"""
    
    test_file_path = os.path.join("public", "test_sse.html")
    
    if not os.path.exists(test_file_path):
        raise HTTPException(status_code=404, detail="Test page not found")
    
    with open(test_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    return HTMLResponse(content=html_content)


@router.get("/test-s3", response_class=HTMLResponse)
async def get_s3_test():
    """Тестовая страница для проверки работы с Yandex Object Storage S3"""
    
    test_file_path = os.path.join("public", "test_s3.html")
    
    if not os.path.exists(test_file_path):
        raise HTTPException(status_code=404, detail="S3 test page not found")
    
    with open(test_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    return HTMLResponse(content=html_content)
