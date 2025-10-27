from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    RPC_ENABLED: bool = True
    
    TEMP_DIR: str = 'var/temp'
    MODEL_CAHCE_DIR: str = 'var/model_cache'

settings = Settings()
