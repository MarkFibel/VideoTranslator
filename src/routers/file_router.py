from starlette.status   import HTTP_500_INTERNAL_SERVER_ERROR
from fastapi            import APIRouter, HTTPException, UploadFile


# from ..services.file_service    import FileService
from ..schemas.response_schema  import FileUploadResponse

router = APIRouter(prefix='/files', tags=["files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile) -> FileUploadResponse:
    try:
        # result = file_service.upload(file)
        
        result = {"filename": file.filename, "content_type": file.content_type, "preview": await file.read(100)}
        
        if result:
            return FileUploadResponse(status="success", message="File uploaded successfully", data=result)
        return FileUploadResponse(status="error", message="File upload failed")
    except Exception as e:
        raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, str(e))
    
