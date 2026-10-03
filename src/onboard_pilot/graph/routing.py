"""Routing: the policy engine (plan.md §6.3). Pure functions, no state mutation, no LLM."""
from typing import Any, Literal

from config.settings import get_settings

CONFLICT_CITATIONS = ("§3.2", "§6.4")


def _max_retries() -> int:
    return get_settings().max_retries


def _rag_threshold() -> float:
    return get_settings().rag_score_threshold


def conflicting_policy_detected(state: Any) -> bool:
    """Heuristic for the planted §3.2/§6.4 contradiction.

    True iff the plan cites both §3.2 and §6.4 and the hire is remote_nl.
    """
    plan = state.plan
    if plan is None or state.form.location != "remote_nl":
        return False
    cited = {c.replace("§ ", "§").strip() for c in plan.policy_citations}
    return all(c in cited for c in CONFLICT_CITATIONS)


def _low_rag_score(state: Any) -> bool:
    return state.rag_min_score is not None and state.rag_min_score < _rag_threshold()


def route_after_validation(state: Any) -> Literal["finalize", "revise", "escalate"]:
    """Decide the next node after validation."""
    hard = [v for v in state.violations if v.severity == "hard"]
    soft = [v for v in state.violations if v.severity == "soft"]
    if hard:
        return "escalate"
    if soft and state.retry_count < _max_retries():
        return "revise"
    if soft:
        return "escalate"
    if _low_rag_score(state) or conflicting_policy_detected(state):
        return "escalate"
    return "finalize"


def build_escalation_reason(state: Any) -> str:
    """Format every escalation trigger present in `state` into one string (P8)."""
    reasons: list[str] = []
    hard = [v for v in state.violations if v.severity == "hard"]
    soft = [v for v in state.violations if v.severity == "soft"]
    if hard:
        reasons.append(
            "Hard policy violation(s): " + "; ".join(f"{v.code} ({v.message})" for v in hard)
        )
    if soft and state.retry_count >= _max_retries():
        reasons.append(
            f"Retries exhausted ({state.retry_count}/{_max_retries()}) with unresolved soft "
            "violation(s): " + "; ".join(f"{v.code} ({v.message})" for v in soft)
        )
    if _low_rag_score(state):
        reasons.append(
            f"Low policy-retrieval confidence: min RAG score {state.rag_min_score:.2f} < "
            f"threshold {_rag_threshold():.2f}"
        )
    if conflicting_policy_detected(state):
        reasons.append(
            "Conflicting policy detected: plan cites both §3.2 (budget caps) and §6.4 "
            "(remote monitor allowance) for a remote_nl hire"
        )
    return " | ".join(reasons) if reasons else "Escalated without a recorded trigger"
