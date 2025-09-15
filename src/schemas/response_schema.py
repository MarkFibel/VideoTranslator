from pydantic import BaseModel


class BaseResponse(BaseModel):
    status: str
    message: str|None
    error: str|None = None


class FileUploadResponse(BaseResponse):
    data: dict | None = None