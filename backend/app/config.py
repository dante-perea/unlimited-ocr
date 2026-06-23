"""Application settings.

Settings are loaded from environment variables and an optional ``.env`` file
(see ``.env.example``). Values are read once and cached via ``get_settings``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Field names map to environment variables case-insensitively, so
    ``CORS_ORIGINS`` in the environment populates ``cors_origins`` here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Unlimited-OCR Backend"
    environment: str = "development"

    # Comma-separated list of origins allowed by CORS (the frontend dev server).
    cors_origins: str = "http://localhost:3000"

    # Optional compute-device override: "cuda" | "mps" | "cpu".
    # Leave empty/None to auto-detect (see app.utils.device).
    device: str | None = None

    # Filesystem locations used by later tasks (PDF downloads, OCR output).
    data_dir: str = "./data"

    # HuggingFace cache directory for model weights (populated by the OCR task).
    hf_home: str = "./.cache/huggingface"

    @property
    def cors_origins_list(self) -> list[str]:
        """Return ``cors_origins`` parsed into a clean list of origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
