from datetime import datetime
import logging
from starlette.status   import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi            import APIRouter, HTTPException, UploadFile

from ..schemas.response_schema  import FileUploadResponse

router = APIRouter(prefix='/files', tags=["files"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile,
) -> FileUploadResponse:
    logger.info(f"File upload started. Filename: {file.filename}, Content-Type: {file.content_type}")
    
    try:
        return FileUploadResponse(
            status="success",
            message="File uploaded successfully. Processing started in background.",
            data={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file.size,
                "upload_time": datetime.utcnow()
            }
        )
    
    except HTTPException:
        raise
        
    except Exception as e:
        # Любые другие ошибки
        logger.error(f"Unexpected file upload error: {str(e)}", exc_info=True)
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Internal server error: {str(e)}")