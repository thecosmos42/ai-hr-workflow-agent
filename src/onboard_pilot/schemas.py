"""All Pydantic schemas for onboarding workflow."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class IntakeForm(BaseModel):
    """Intake form submitted by hiring manager."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    full_name: str
    email: EmailStr
    role: Literal[
        "software_engineer",
        "data_analyst",
        "finance_officer",
        "hr_coordinator",
        "sales_rep",
        "engineering_manager",
    ]
    level: Literal["junior", "medior", "senior", "lead"]
    department: Literal["engineering", "data", "finance", "hr", "sales"]
    start_date: date
    manager_email: EmailStr
    location: Literal["eindhoven_office", "amsterdam_office", "remote_nl"]
    contract_type: Literal["permanent", "fixed_term", "contractor"]
    visa_required: bool
    accessibility_needs: str | None = None
    requested_extras: list[str] = Field(default_factory=list)


class AccessRequest(BaseModel):
    """Request for system access."""

    model_config = ConfigDict(extra="forbid")

    system: str
    justification: str


class EquipmentItem(BaseModel):
    """Equipment to order."""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    name: str
    price_eur: float
    quantity: int = 1


class ScheduledEvent(BaseModel):
    """Scheduled onboarding event."""

    model_config = ConfigDict(extra="forbid")

    title: str
    event_type: Literal[
        "it_setup",
        "manager_1on1",
        "buddy_lunch",
        "compliance_training",
        "security_training",
        "hr_intro",
    ]
    date: date
    duration_minutes: int


class OnboardingTask(BaseModel):
    """Task in onboarding process."""

    model_config = ConfigDict(extra="forbid")

    title: str
    owner: Literal["hr", "it", "manager", "employee"]
    due_date: date


class OnboardingPlan(BaseModel):
    """Complete onboarding plan (LLM output)."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    employee_summary: str
    access_requests: list[AccessRequest] = Field(default_factory=list)
    equipment: list[EquipmentItem] = Field(default_factory=list)
    schedule: list[ScheduledEvent] = Field(default_factory=list)
    tasks: list[OnboardingTask] = Field(default_factory=list)
    policy_citations: list[str] = Field(default_factory=list)


class PolicyViolation(BaseModel):
    """Policy violation detected during validation."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["hard", "soft"]
    message: str
    field_path: str
    policy_ref: str


class ToolResult(BaseModel):
    """Uniform result from any tool."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    ok: bool
    data: dict | list | None = None
    error_code: str | None = None
    error_message: str | None = None


class OnboardingState(BaseModel):
    """LangGraph state for onboarding workflow."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    form: IntakeForm
    plan: OnboardingPlan | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    violations: list[PolicyViolation] = Field(default_factory=list)
    retry_count: int = 0
    status: Literal[
        "running", "auto_approved", "escalated", "approved_by_human", "rejected_by_human", "finalized"
    ] = "running"
    escalation_reason: str | None = None
    human_decision: Literal["approve", "reject"] | None = None
    human_comment: str | None = None
    rag_min_score: float | None = None
    audit_events: list[dict] = Field(default_factory=list)
