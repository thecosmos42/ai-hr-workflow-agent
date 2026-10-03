"""Configuration and settings."""
import os
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # LLM configuration (DEVIATIONS P13)
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_tokens: int = 4096
    anthropic_api_key: str = ""

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "onboard.db"
    checkpoints_db_path: Path = data_dir / "checkpoints.db"
    chroma_dir: Path = data_dir / "chroma"

    # Validation thresholds
    rag_score_threshold: float = 0.35
    max_retries: int = 3

    # Dates (DEVIATIONS P2)
    today_override: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get or create settings singleton."""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = Settings(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
        )
    return get_settings._instance


def get_today() -> date:
    """Get today's date, respecting TODAY_OVERRIDE for testing (DEVIATIONS P2)."""
    settings = get_settings()
    if settings.today_override:
        return date.fromisoformat(settings.today_override)
    return date.today()


# Cost table for token pricing in EUR (DEVIATIONS P12)
# claude-haiku-4-5-20251001 pricing (verified ~2026-10):
# ~$1 per 1M input tokens, ~$5 per 1M output tokens
# Assumed USD→EUR rate: 1 USD = 0.92 EUR (as of 2026-10)
COST_TABLE = {
    "claude-haiku-4-5-20251001": (
        0.92 / 1_000_000,  # input cost in EUR per token
        4.60 / 1_000_000,  # output cost in EUR per token
    )
}
