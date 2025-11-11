"""
Утилиты для работы с Yandex SmartCaptcha.
"""
import logging
import httpx
from typing import Optional

from src.config.app_config import settings

logger = logging.getLogger(__name__)


async def verify_captcha(token: str, user_ip: Optional[str] = None) -> bool:
    """
    Проверяет токен капчи через API Yandex SmartCaptcha.
    
    :param token: Токен капчи от клиента
    :param user_ip: IP адрес пользователя (опционально)
    :return: True если капча пройдена, False иначе
    """
    # Если капча отключена в настройках - пропускаем проверку
    if not settings.CAPTCHA_ENABLED:
        logger.debug("Captcha verification skipped (disabled in settings)")
        return True
    
    # Если нет серверного ключа - пропускаем (для разработки)
    if not settings.CAPTCHA_SERVER_KEY:
        logger.warning("CAPTCHA_SERVER_KEY not set, skipping verification")
        return True
    
    # Если токен пустой - капча не пройдена
    if not token:
        logger.warning("Captcha token is empty")
        return False
    
    try:
        # URL для проверки Yandex SmartCaptcha
        url = "https://smartcaptcha.yandexcloud.net/validate"
        
        # Параметры запроса
        params = {
            "secret": settings.CAPTCHA_SERVER_KEY,
            "token": token
        }
        
        # Добавляем IP если указан
        if user_ip:
            params["ip"] = user_ip
        
        # Отправляем GET запрос к API Yandex
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Captcha API returned status {response.status_code}: {response.text}")
                return False
            
            result = response.json()
            
            # Проверяем результат
            # Документация: https://yandex.cloud/ru/docs/smartcaptcha/api-ref/
            status = result.get("status")
            
            if status == "ok":
                logger.info("Captcha verification successful")
                return True
            else:
                logger.warning(f"Captcha verification failed: {result}")
                return False
                
    except httpx.TimeoutException:
        logger.error("Captcha verification timeout")
        # В случае таймаута можем либо пропустить, либо заблокировать
        # Для безопасности лучше заблокировать
        return False
        
    except Exception as e:
        logger.error(f"Captcha verification error: {e}", exc_info=True)
        # В случае ошибки можем либо пропустить, либо заблокировать
        # Для безопасности лучше заблокировать
        return False


def get_client_ip(request) -> Optional[str]:
    """
    Извлекает IP адрес клиента из запроса.
    Учитывает proxy заголовки.
    
    :param request: FastAPI Request объект
    :return: IP адрес клиента или None
    """
    # Проверяем заголовки прокси
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For может содержать несколько IP через запятую
        # Берем первый (клиентский)
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback на прямой IP
    if request.client:
        return request.client.host
    
    return None
