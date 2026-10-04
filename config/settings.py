"""Configuration and settings."""
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

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


def get_settings() -> Settings:
    """Get or create settings singleton."""
    if not hasattr(get_settings, "_instance"):
        get_settings._instance = Settings()
    return get_settings._instance


POLICY_TABLES_PATH = Path(__file__).parent / "policy_tables.yaml"


@lru_cache(maxsize=1)
def load_policy_tables() -> dict:
    """Load config/policy_tables.yaml (cached). Treat the result as read-only."""
    with open(POLICY_TABLES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_today() -> date:
    """Get today's date, respecting TODAY_OVERRIDE for testing (DEVIATIONS P2)."""
    settings = get_settings()
    if settings.today_override:
        return date.fromisoformat(settings.today_override)
    return date.today()
