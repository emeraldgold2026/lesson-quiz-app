from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    database_url: str = "sqlite:///data/app.db"
    upload_dir: str = "data/uploads"
    cors_origins: list[str] = ["http://localhost:3000"]
