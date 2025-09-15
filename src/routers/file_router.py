import logging
from starlette.status   import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi            import APIRouter, HTTPException, UploadFile, Request, Depends
from fastapi_csrf_protect import CsrfProtect

from ..services.file_service    import FileService
from ..services.csrf_service    import validate_csrf_token_availability, csrf_token_manager, CSRFProtectionError
from ..schemas.response_schema  import FileUploadResponse

router = APIRouter(prefix='/files', tags=["files"])
file_service = FileService()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile, 
    request: Request,
    csrf_protect: CsrfProtect = Depends()
) -> FileUploadResponse:
    logger.info(f"File upload started. Filename: {file.filename}, Content-Type: {file.content_type}")
    
    csrf_token = None
    try:
        # Проверяем CSRF токен
        await csrf_protect.validate_csrf(request)
        
        # Получаем токен из заголовков для нашего менеджера DoS защиты
        csrf_token = request.headers.get('X-CSRF-Token')
        
        if not csrf_token or not isinstance(csrf_token, str):
            logger.warning("CSRF token not found in request headers")
            raise HTTPException(400, "CSRF token is required")
        
        # СТРОГАЯ ПРОВЕРКА: Проверяем доступность токена и сразу блокируем его
        if not csrf_token_manager.acquire_token(csrf_token):
            logger.warning(f"Token {csrf_token[:8]}... is already being processed (DoS protection triggered)")
            raise CSRFProtectionError(
                "This request is already being processed. Please wait for completion before submitting again."
            )
        
        logger.info(f"CSRF token validated and locked: {csrf_token[:8]}...")
        
        try:
            # Выполняем загрузку файла
            result = await file_service.upload(file)
            
            if result:
                logger.info(f"File uploaded successfully. UUID: {result['uuid']}, Size: {result['size']} bytes")
                return FileUploadResponse(status="success", message="File uploaded successfully", data=result)
            
            logger.warning("File upload failed: No result returned from file service")
            return FileUploadResponse(status="error", message="File upload failed")
            
        except Exception as upload_error:
            logger.error(f"File upload processing error: {str(upload_error)}", exc_info=True)
            raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"File upload failed: {str(upload_error)}")
            
        finally:
            # ОБЯЗАТЕЛЬНО освобождаем токен после завершения обработки
            if csrf_token:
                csrf_token_manager.release_token(csrf_token)
                logger.info(f"CSRF token unlocked: {csrf_token[:8]}...")
            
    except CSRFProtectionError:
        # Повторный запрос с тем же токеном - возвращаем специальную ошибку
        logger.warning("DoS protection: Duplicate request blocked")
        raise
        
    except HTTPException:
        # Пробрасываем HTTP исключения как есть
        if csrf_token:
            csrf_token_manager.release_token(csrf_token)
        raise
        
    except Exception as e:
        # Любые другие ошибки
        logger.error(f"Unexpected file upload error: {str(e)}", exc_info=True)
        if csrf_token:
            csrf_token_manager.release_token(csrf_token)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Internal server error: {str(e)}")


@router.get("/token-stats")
async def get_token_stats():
    """Получить статистику по CSRF токенам (для отладки)"""
    stats = csrf_token_manager.get_stats()
    logger.info(f"Token statistics requested: {stats}")
    return {
        "status": "success",
        "data": stats,
        "message": f"Active tokens: {stats['active_tokens']}, Total tokens: {stats['total_tokens']}"
    }