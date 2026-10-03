"""Routing tests: pure functions over OnboardingState. No LLM, no network."""
from datetime import date

from onboard_pilot.graph.routing import (
    build_escalation_reason,
    conflicting_policy_detected,
    route_after_validation,
)
from onboard_pilot.schemas import (
    IntakeForm,
    OnboardingPlan,
    OnboardingState,
    PolicyViolation,
)


def make_form(location="amsterdam_office") -> IntakeForm:
    return IntakeForm(
        case_id="case-1", full_name="N T", email="n@example.com", role="finance_officer",
        level="junior", department="finance", start_date=date(2026, 10, 20),
        manager_email="anna.visser@corp.example", location=location,
        contract_type="permanent", visa_required=False,
    )


def make_state(violations=(), retry_count=0, rag=None, citations=(), location="amsterdam_office",
               plan=True) -> OnboardingState:
    p = OnboardingPlan(case_id="case-1", employee_summary="x",
                       policy_citations=list(citations)) if plan else None
    return OnboardingState(
        case_id="case-1", form=make_form(location), plan=p,
        violations=list(violations), retry_count=retry_count, rag_min_score=rag,
    )


def viol(severity, code="X") -> PolicyViolation:
    return PolicyViolation(code=code, severity=severity, message=f"{code} msg",
                           field_path="f", policy_ref="§1")


def test_hard_escalates_even_with_retries_left():
    assert route_after_validation(make_state([viol("hard", "MANAGER_NOT_FOUND")], retry_count=0)) \
        == "escalate"


def test_hard_plus_soft_escalates():
    s = make_state([viol("soft"), viol("hard")], retry_count=0)
    assert route_after_validation(s) == "escalate"


def test_soft_with_retries_left_revises():
    for rc in (0, 1, 2):
        assert route_after_validation(make_state([viol("soft")], retry_count=rc)) == "revise"


def test_soft_retries_exhausted_escalates():
    assert route_after_validation(make_state([viol("soft")], retry_count=3)) == "escalate"
    assert route_after_validation(make_state([viol("soft")], retry_count=5)) == "escalate"


def test_clean_low_rag_escalates():
    assert route_after_validation(make_state(rag=0.2)) == "escalate"


def test_clean_rag_at_threshold_finalizes():
    assert route_after_validation(make_state(rag=0.35)) == "finalize"


def test_clean_no_rag_score_finalizes():
    assert route_after_validation(make_state(rag=None)) == "finalize"


def test_clean_conflicting_citations_remote_escalates():
    s = make_state(citations=["§3.2", "§6.4"], location="remote_nl", rag=0.9)
    assert conflicting_policy_detected(s) is True
    assert route_after_validation(s) == "escalate"


def test_same_citations_not_remote_finalizes():
    s = make_state(citations=["§3.2", "§6.4"], location="amsterdam_office", rag=0.9)
    assert conflicting_policy_detected(s) is False
    assert route_after_validation(s) == "finalize"


def test_remote_with_only_one_citation_finalizes():
    for c in (["§3.2"], ["§6.4"]):
        s = make_state(citations=c, location="remote_nl", rag=0.9)
        assert conflicting_policy_detected(s) is False
        assert route_after_validation(s) == "finalize"


def test_citations_with_spaced_section_sign_still_detected():
    s = make_state(citations=["§ 3.2", "§ 6.4"], location="remote_nl")
    assert conflicting_policy_detected(s) is True


def test_conflict_with_no_plan_is_false():
    assert conflicting_policy_detected(make_state(plan=False, location="remote_nl")) is False


def test_clean_finalizes():
    assert route_after_validation(make_state(citations=["§3.2"], rag=0.8)) == "finalize"


def test_route_does_not_mutate_state():
    s = make_state([viol("hard")])
    before = s.model_dump()
    route_after_validation(s)
    build_escalation_reason(s)
    assert s.model_dump() == before


def test_route_returns_only_valid_literals():
    states = [make_state(), make_state([viol("soft")]), make_state([viol("hard")]),
              make_state([viol("soft")], retry_count=3), make_state(rag=0.0)]
    assert {route_after_validation(s) for s in states} <= {"finalize", "revise", "escalate"}


def test_reason_names_hard_violation():
    r = build_escalation_reason(make_state([viol("hard", "PRIVILEGED_ACCESS_REQUEST")]))
    assert "PRIVILEGED_ACCESS_REQUEST" in r and "Hard" in r


def test_reason_names_retries_exhausted():
    r = build_escalation_reason(make_state([viol("soft", "BUDGET_EXCEEDED")], retry_count=3))
    assert "Retries exhausted" in r and "3/3" in r and "BUDGET_EXCEEDED" in r


def test_reason_names_low_rag():
    r = build_escalation_reason(make_state(rag=0.21))
    assert "0.21" in r and "0.35" in r


def test_reason_names_conflict():
    r = build_escalation_reason(
        make_state(citations=["§3.2", "§6.4"], location="remote_nl", rag=0.9))
    assert "§3.2" in r and "§6.4" in r


def test_reason_names_every_trigger_at_once():
    s = make_state([viol("hard", "MANAGER_NOT_FOUND"), viol("soft", "TRAINING_MISSING")],
                   retry_count=3, rag=0.1, citations=["§3.2", "§6.4"], location="remote_nl")
    r = build_escalation_reason(s)
    for needle in ("MANAGER_NOT_FOUND", "TRAINING_MISSING", "Retries exhausted",
                   "Low policy-retrieval", "Conflicting policy"):
        assert needle in r
