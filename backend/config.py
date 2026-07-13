from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/aiagent"
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    memory_window: int = 20  # last N messages to include as context

    class Config:
        env_file = ".env"


settings = Settings()
