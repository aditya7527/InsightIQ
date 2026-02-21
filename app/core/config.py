from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./insightiq.db"
    jwt_secret: str = "replace_this_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    gemini_api_key: Optional[str] = None
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    upload_dir: str = "./data/uploads"
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
