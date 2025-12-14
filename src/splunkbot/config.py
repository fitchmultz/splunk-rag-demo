"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str = "splunkbot"
    postgres_password: str = "splunkbot"
    postgres_db: str = "splunkbot"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Ollama
    ollama_host: str = "http://localhost:11434"
    chat_model: str = "gpt-oss:20b"
    embedding_model: str = "bge-m3"
    embedding_dimensions: int = 1024

    # Retrieval
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    rrf_k: int = 60

    # Application
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """Build the database connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# Global settings instance
settings = Settings()
