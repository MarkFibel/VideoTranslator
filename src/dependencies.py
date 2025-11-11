"""
FastAPI dependencies для проверки капчи и других общих задач.
"""
from fastapi import HTTPException, Request, Form
from typing import Optional
import logging

from src.utils.captcha_utils import verify_captcha, get_client_ip

logger = logging.getLogger(__name__)


async def verify_captcha_token(
    request: Request,
    captcha_token: Optional[str] = Form(None, alias="captcha_token")
) -> None:
    """
    FastAPI dependency для проверки токена капчи.
    
    :param request: FastAPI Request
    :param captcha_token: Токен капчи из формы
    :raises HTTPException: Если капча не пройдена
    """
    # Получаем IP клиента
    client_ip = get_client_ip(request)
    
    # Проверяем капчу
    is_valid = await verify_captcha(captcha_token or "", client_ip)
    
    if not is_valid:
        logger.warning(f"Captcha verification failed for IP: {client_ip}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CAPTCHA_FAILED",
                "detail": "Проверка капчи не пройдена. Пожалуйста, попробуйте снова."
            }
        )
