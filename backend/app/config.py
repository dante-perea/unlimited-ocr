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

    # HuggingFace cache directory for model weights (downloaded by the OCR task).
    hf_home: str = "./.cache/huggingface"

    # Directory where cached source PDFs live. The (separate) NCBI task downloads
    # PMC Open Access PDFs here; the OCR task reads them. Defaults to data_dir/pdfs.
    pdf_cache_dir: str = ""

    # ---- OCR pipeline ----
    # MOCK / offline mode: when true, skip loading the real model and return
    # canned OCR output. Lets the frontend be built/developed without a GPU.
    ocr_mock: bool = False

    # HuggingFace model id (or local path) for Unlimited-OCR.
    ocr_model_name: str = "baidu/Unlimited-OCR"

    # DPI used when rasterizing PDF pages to PNG for OCR (upstream example: 300).
    ocr_pdf_dpi: int = 300

    # Hard cap on the number of pages processed per run (0 = no cap). Protects
    # against pathological documents blowing up memory/time on the GPU.
    ocr_max_pages: int = 0

    # Which facts extractor to use. "heuristic" is the built-in baseline; other
    # names may be registered via app.services.facts.register_fact_extractor.
    facts_extractor: str = "heuristic"

    # ---- NCBI E-utilities / PMC Open Access ----
    # Optional NCBI API key. When set, the E-utility rate limit is raised from
    # 3 requests/second to 10. Get one at:
    #   https://www.ncbi.nlm.nih.gov/account/settings/
    ncbi_api_key: str = ""

    # `tool` / `email` values sent with every E-utility request (NCBI policy).
    ncbi_tool: str = "unlimited-ocr-backend"
    ncbi_email: str = ""

    # E-utility + PMC OA Web Service base URLs (rarely need changing).
    ncbi_eutils_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    ncbi_oa_base_url: str = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"

    # HTTP timeout (seconds) for upstream NCBI/PMC requests.
    ncbi_request_timeout: float = 30.0

    @property
    def cors_origins_list(self) -> list[str]:
        """Return ``cors_origins`` parsed into a clean list of origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def pdf_cache_dir_resolved(self) -> str:
        """Return the PDF cache dir, defaulting to ``data_dir/pdfs``."""
        return self.pdf_cache_dir.strip() or f"{self.data_dir.rstrip('/')}/pdfs"

    @property
    def ncbi_has_api_key(self) -> bool:
        """Whether an NCBI API key is configured."""
        return bool(self.ncbi_api_key)

    @property
    def ncbi_rate_per_second(self) -> float:
        """Maximum E-utility requests/second given the current key (3 or 10)."""
        return 10.0 if self.ncbi_api_key else 3.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
