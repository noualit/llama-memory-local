from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str
    LLAMA_SERVER_BASE_URL: str
    EMBEDDING_MODEL_URL: str
    EMBEDDING_MODEL_NAME: str = "nomic-embed-text"
    SERVICE_PORT: int = 9001


settings = Settings()
