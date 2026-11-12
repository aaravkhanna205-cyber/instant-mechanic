from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = ""
    redis_url: str = ""
    cors_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    # Optional local AI (Ollama) for drafting interview questions. Empty = rule-based drafts only.
    ollama_url: str = ""
    ollama_model: str = "llama3.2:3b"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return list(dict.fromkeys(
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
