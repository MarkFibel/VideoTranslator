from dotenv import load_dotenv

from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    RPC_ENABLED: bool = False
    
settings = Settings()