from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:password@db:5432/insightiq"
    jwt_secret: str = "replace_this_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    upload_dir: str = "./data/uploads"
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
