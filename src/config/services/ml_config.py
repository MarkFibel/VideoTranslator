from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar

load_dotenv()


class Settings(BaseSettings):
    # ===== Runtime flags =====
    RPC_ENABLED: bool = True

    # ===== ML Service Settings =====
    remote_url: str|None = None

    sse_timeout: int = 300  # seconds
    sinchronous_timeout: int = 900  # seconds

settings = Settings()
