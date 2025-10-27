from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    RPC_ENABLED: bool = Field(default=True, exclude=True)
    
    TEMP_DIR: str = 'var/temp'
    MODEL_CACHE_DIR: str = 'var/model_cache'

settings = Settings()
