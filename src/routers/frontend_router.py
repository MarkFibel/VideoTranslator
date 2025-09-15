import logging
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi_csrf_protect import CsrfProtect
from ..services.csrf_service import csrf_token_manager

router = APIRouter(tags=["frontend"])
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def get_index(csrf_protect: CsrfProtect = Depends()):
    """Обслуживание главной страницы с автоматической выдачей CSRF токена"""
    logger.info("Serving index.html with CSRF token")
    
    # Генерируем CSRF токен и устанавливаем cookie
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    
    # Читаем HTML файл
    with open("public/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Вставляем токен в HTML как JavaScript переменную
    csrf_script = f"""
    <script>
        window.csrfToken = '{csrf_token}';
        console.log('CSRF token loaded:', window.csrfToken);
    </script>
    """
    
    # Вставляем скрипт перед закрывающим тегом head
    html_content = html_content.replace("</head>", csrf_script + "</head>")
    
    # Создаем response с модифицированным HTML
    response = HTMLResponse(content=html_content)
    
    # Устанавливаем CSRF cookie для валидации на сервере
    csrf_protect.set_csrf_cookie(signed_token, response)
    
    # Регистрируем токен в нашем менеджере
    csrf_token_manager.register_new_token(csrf_token)
    logger.debug(f"CSRF token registered: {csrf_token[:8]}...")
    
    return response