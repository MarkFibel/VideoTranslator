# VideoTranslator - AI Coding Agent Instructions

## Project Overview
VideoTranslator is a FastAPI-based microservice backend for video processing and translation. The architecture separates HTTP API handling from async background processing using RabbitMQ message queues.

## Architecture Principles

### Two-Layer Design
1. **API Server** (`src/app.py`) - FastAPI application handling HTTP requests
2. **Service Handlers** (planned) - Background workers consuming RabbitMQ tasks for video processing

### Key Design Patterns
- **Factory Pattern**: Application initialization via `get_application()` in `src/app.py`
- **Router Composition**: Modular routers combined in `src/routes.py` via `get_apps_router()`
- **Pydantic Settings**: Environment-based configuration in `src/config/app_config.py` with `.env` support
- **Async-First**: All route handlers and services use `async def` for non-blocking I/O

## Project Structure

```
src/
├── app.py                    # FastAPI app factory, static file mounting
├── routes.py                 # Router aggregation point
├── config/                   # Settings & logging configuration
│   ├── app_config.py         # Pydantic Settings (env vars, file size limits)
│   └── logging_config.py     # Multi-handler logging (console, file, error)
├── routers/                  # HTTP endpoints (prefix-based organization)
│   ├── file_router.py        # /files/* - File upload endpoints
│   └── frontend_router.py    # / - Static HTML serving
├── schemas/                  # Pydantic models for request/response validation
│   ├── base_schema.py        # Base models with from_attributes=True
│   └── response_schema.py    # Standardized API responses (BaseResponse, FileUploadResponse)
└── services/                 # Business logic (currently file_service.py is empty)
```

## Critical Development Patterns

### 1. Response Schema Convention
All API responses must use schema classes from `src/schemas/response_schema.py`:
- `BaseResponse` for simple operations (status, message, error fields)
- `FileUploadResponse` for file operations (adds data dict)
- Always return structured JSON, even for errors

Example:
```python
return FileUploadResponse(
    status="success",
    message="File uploaded successfully. Processing started in background.",
    data={"filename": file.filename, "content_type": file.content_type}
)
```

### 2. Error Handling Pattern
```python
try:
    # Business logic
except HTTPException:
    raise  # Re-raise HTTP exceptions as-is
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    raise HTTPException(HTTP_500_INTERNAL_SERVER_ERROR, f"Internal server error: {str(e)}")
```

### 3. Logging Standards
- Import logger: `logger = logging.getLogger(__name__)`
- Log at entry: `logger.info(f"Operation started. Param: {param}")`
- Log errors: `logger.error(f"Error details", exc_info=True)`
- Logs go to `var/log/app.log` (info) and `var/log/error.log` (errors) with 10MB rotation

### 4. Router Organization
- Each router uses `APIRouter(prefix='/resource', tags=["resource"])`
- Register routers in `src/routes.py` via `router.include_router()`
- Frontend router has NO prefix (serves root `/`)
- API routers use resource-based prefixes (`/files`, `/tasks`, etc.)

### 5. Configuration Access
```python
from src.config.app_config import settings

# Access settings
max_size = settings.MAX_FILE_SIZE
log_level = settings.LOG_LEVEL
```

## Technology Stack

### Core Dependencies
- **FastAPI** - Web framework (v0.116.1)
- **Uvicorn** - ASGI server for development/production
- **Pydantic v2** - Data validation and settings management
- **aio-pika** - Async RabbitMQ client (not yet implemented)
- **aiofiles** - Async file I/O operations
- **python-multipart** - File upload handling

### Development Commands
```powershell
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

# Run from app.py directly
python -m src.app

# Check logs
Get-Content var/log/app.log -Tail 50
Get-Content var/log/error.log -Tail 50
```

## Frontend Integration

- Static files served from `public/` directory mounted at `/static`
- Main HTML at `public/index.html` served by `frontend_router.py` at `/`
- Frontend uses Tailwind CSS (CDN) with custom "terminal/matrix" green theme
- No template engine - direct HTML file reading in `get_index()` endpoint

## Planned Features (Not Yet Implemented)

- **RabbitMQ Integration**: API will push tasks to queue after file validation
- **Background Workers**: Separate processes consuming queue for video processing
- **JSON-RPC**: Inter-service communication protocol
- **File Service**: Async file storage/retrieval in `src/services/file_service.py`

## Common Pitfall Avoidance

1. **Don't forget async**: All new route handlers MUST be `async def`
2. **Always validate file size**: Check against `settings.MAX_FILE_SIZE` (10MB default)
3. **Use structured responses**: Never return plain dicts - use response schemas
4. **Log before exceptions**: Add context logging before raising HTTPException
5. **Static path mounting**: Static files are at `/static/*`, not `/public/*`

## When Adding New Features

1. **New endpoint**: Create router in `src/routers/`, register in `src/routes.py`
2. **New config**: Add to `Settings` class in `app_config.py` with `.env` support
3. **New schema**: Inherit from `BaseResponse` or `Base` in `src/schemas/`
4. **New service**: Create in `src/services/`, use async methods, inject via dependencies
5. **Error handling**: Follow the try-except pattern shown above

## Testing Approach
Currently no test framework configured. Manual testing via:
- Browser: `http://localhost:8000/`
- API: `http://localhost:8000/files/upload` (POST with file)
- FastAPI docs: `http://localhost:8000/docs` (auto-generated Swagger UI)
