"""Single LLM factory and token pricing (DEVIATIONS P12, P13)."""
import logging

from langchain_anthropic import ChatAnthropic

from config.settings import get_settings

logger = logging.getLogger(__name__)

# EUR per 1M tokens as (input, output) for claude-haiku-4-5-20251001.
# Believed list price ~$1 in / ~$5 out per 1M tokens; assumed 1 USD = 0.92 EUR (2026-10).
# Pricing is unverified against Anthropic's price page: re-check before quoting costs.
COST_TABLE: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.92, 4.60),
}


def get_llm() -> ChatAnthropic:
    """Return the Claude Haiku 4.5 chat model. The only place an LLM is constructed."""
    settings = get_settings()
    kwargs: dict = {}
    if settings.anthropic_api_key:
        kwargs["api_key"] = settings.anthropic_api_key
    return ChatAnthropic(
        model=settings.llm_model,
        temperature=0,
        max_tokens=settings.llm_max_tokens,
        **kwargs,
    )


def compute_cost_eur(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost in EUR for a token count; 0.0 (with a warning) for a model not in COST_TABLE."""
    prices = COST_TABLE.get(model)
    if prices is None:
        logger.warning("No cost table entry for model %s", model)
        return 0.0
    return (tokens_in * prices[0] + tokens_out * prices[1]) / 1_000_000
