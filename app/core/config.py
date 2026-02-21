from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List, Union
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
    cors_origins: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    upload_dir: str = "./data/uploads"
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_db_url(cls, value):
        if not value:
            return "sqlite:///./insightiq.db"
        
        if isinstance(value, str):
            value = value.strip()
            
        # If user just pasted the hostname like 'trolley.proxy.rlwy.net'
        if "://" not in value:
            # We can't know the password, so we must error but with a better message
            raise ValueError(
                f"Invalid DATABASE_URL: '{value}'. "
                "It must start with 'postgresql://' or 'sqlite:///'. "
                "In Railway, copy the FULL 'DATABASE_URL' from the Variables tab, not just the hostname."
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            # If it's a JSON-like list string, try to parse it as JSON
            if value.startswith("[") and value.endswith("]"):
                try:
                    import json
                    return json.loads(value)
                except:
                    pass
            # Fallback to comma-separated string
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
