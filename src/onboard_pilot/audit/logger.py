"""Audit logging: `@log_node` decorator writing one `audit_log` row per node execution."""
import functools
import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable

from config.settings import get_settings
from onboard_pilot import db
from onboard_pilot.llm import compute_cost_eur

logger = logging.getLogger(__name__)

_tokens_in: ContextVar[int] = ContextVar("audit_tokens_in", default=0)
_tokens_out: ContextVar[int] = ContextVar("audit_tokens_out", default=0)
_summary: ContextVar[str | None] = ContextVar("audit_summary", default=None)
_payload: ContextVar[dict | None] = ContextVar("audit_payload", default=None)


def record_usage(message: Any) -> None:
    """Add the token usage of an LLM response (reads `usage_metadata`) to the current node."""
    usage = getattr(message, "usage_metadata", None) or {}
    _tokens_in.set(_tokens_in.get() + int(usage.get("input_tokens", 0)))
    _tokens_out.set(_tokens_out.get() + int(usage.get("output_tokens", 0)))


def set_summary(summary: str) -> None:
    """Set the short outcome text for the current node's audit row."""
    _summary.set(summary)


def set_payload(payload: dict) -> None:
    """Set the rich payload (violations, tool results, plan diff...) for the current node."""
    _payload.set(payload)


def write_audit_row(
    *,
    run_id: str,
    case_id: str,
    node: str,
    attempt: int,
    tokens_in: int,
    tokens_out: int,
    cost_eur: float,
    latency_ms: int,
    summary: str,
    payload: dict | None,
    ts: str,
) -> None:
    """Insert one row into `audit_log`."""
    conn = db.get_connection(get_settings().db_path)
    try:
        conn.execute(
            """
            INSERT INTO audit_log (run_id, case_id, ts, node, attempt, tokens_in, tokens_out,
                                   cost_eur, latency_ms, summary, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, case_id, ts, node, attempt, tokens_in, tokens_out, cost_eur,
                latency_ms, summary, json.dumps(payload or {}, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def log_node(node_name: str) -> Callable:
    """Decorator for graph nodes `fn(state) -> dict`.

    Captures latency and token usage, writes an `audit_log` row, and appends a compact
    event to `state.audit_events`. The run id comes from `config["configurable"]["run_id"]`.
    """

    def decorator(fn: Callable) -> Callable:
        def wrapper(state, config=None):
            _tokens_in.set(0)
            _tokens_out.set(0)
            _summary.set(None)
            _payload.set(None)
            start = time.perf_counter()
            update = fn(state) or {}
            latency_ms = int((time.perf_counter() - start) * 1000)

            configurable = (config or {}).get("configurable", {})
            run_id = configurable.get("run_id") or f"{state.case_id}-{uuid.uuid4().hex[:8]}"
            tokens_in, tokens_out = _tokens_in.get(), _tokens_out.get()
            cost = compute_cost_eur(get_settings().llm_model, tokens_in, tokens_out)
            summary = _summary.get() or "ok"
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            attempt = update.get("retry_count", state.retry_count)

            write_audit_row(
                run_id=run_id, case_id=state.case_id, node=node_name, attempt=attempt,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_eur=cost,
                latency_ms=latency_ms, summary=summary, payload=_payload.get(), ts=ts,
            )
            event = {
                "node": node_name, "attempt": attempt, "ts": ts, "summary": summary,
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "cost_eur": cost, "latency_ms": latency_ms,
            }
            update["audit_events"] = [*state.audit_events, event]
            return update

        # Copy metadata but not __wrapped__: LangGraph must see the (state, config) signature.
        functools.update_wrapper(wrapper, fn)
        del wrapper.__wrapped__
        return wrapper

    return decorator
