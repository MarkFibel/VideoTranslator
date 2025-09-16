"""
Middleware для защиты от некорректных HTTP запросов
Предотвращает ошибки "Invalid HTTP request received" в uvicorn
"""
import logging
import re
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware для защиты от аномальных HTTP запросов
    """
    
    def __init__(self, app, max_request_size: int = 1024 * 1024):  # 1MB
        super().__init__(app)
        self.max_request_size = max_request_size
        
        # Паттерны для обнаружения подозрительных запросов
        self.suspicious_patterns = [
            r't3\s+\d+\.\d+',  # WebLogic T3 protocol
            r'\\x[0-9a-f]{2}',  # Hexadecimal sequences
            r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',  # Control characters
        ]
        
        # Подозрительные User-Agent строки
        self.suspicious_user_agents = [
            'scanner', 'bot', 'crawler', 'exploit', 'hack', 
            'attack', 'weblogic', 'oracle', 'vulnerability'
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            # Получаем IP адрес клиента безопасным способом
            client_ip = self._get_client_ip(request)
            
            # Проверяем размер запроса
            if hasattr(request, 'headers'):
                content_length = request.headers.get('content-length')
                if content_length and int(content_length) > self.max_request_size:
                    logger.warning(f"Request too large: {content_length} bytes from {client_ip}")
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request entity too large"}
                    )
            
            # Проверяем User-Agent
            user_agent = request.headers.get('user-agent', '').lower()
            if any(suspicious in user_agent for suspicious in self.suspicious_user_agents):
                logger.warning(f"Suspicious User-Agent blocked: {user_agent} from {client_ip}")
                return JSONResponse(
                    status_code=403,
                    content={"error": "Forbidden"}
                )
            
            # Проверяем URL на подозрительные паттерны
            url_path = str(request.url.path)
            for pattern in self.suspicious_patterns:
                if re.search(pattern, url_path, re.IGNORECASE):
                    logger.warning(f"Suspicious URL pattern detected: {url_path} from {client_ip}")
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Bad request"}
                    )
            
            # Проверяем HTTP метод
            if request.method not in ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD', 'PATCH']:
                logger.warning(f"Invalid HTTP method: {request.method} from {client_ip}")
                return JSONResponse(
                    status_code=405,
                    content={"error": "Method not allowed"}
                )
            
            # Логируем подозрительные IP адреса
            if self._is_suspicious_ip(client_ip):
                logger.info(f"Request from potentially suspicious IP: {client_ip}")
            
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Перехватываем любые исключения, которые могут вызвать проблемы с uvicorn
            logger.error(f"Error in SecurityMiddleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Безопасно получает IP адрес клиента
        """
        if request.client and hasattr(request.client, 'host'):
            return request.client.host
        
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        return 'unknown'
    
    def _is_suspicious_ip(self, ip: str) -> bool:
        """
        Проверяет, является ли IP адрес подозрительным
        """
        # Список известных диапазонов, часто используемых сканерами
        suspicious_ranges = [
            '118.193.',  # Часто встречается в логах атак
            '101.36.',   # Часто встречается в логах атак
            '165.154.',  # Часто встречается в логах атак
        ]
        
        return any(ip.startswith(range_) for range_ in suspicious_ranges)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для детального логирования запросов
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Получаем IP адрес клиента
        client_ip = self._get_client_ip(request)
        
        # Логируем входящий запрос
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {client_ip} "
            f"UA: {request.headers.get('user-agent', 'Unknown')[:100]}"
        )
        
        try:
            response = await call_next(request)
            
            # Логируем ответ
            logger.info(
                f"Response: {response.status_code} for "
                f"{request.method} {request.url.path}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Request processing failed"}
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Безопасно получает IP адрес клиента
        """
        if request.client and hasattr(request.client, 'host'):
            return request.client.host
        
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        return 'unknown'