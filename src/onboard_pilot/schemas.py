"""All Pydantic schemas for onboarding workflow."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class IntakeForm(BaseModel):
    """Intake form submitted by hiring manager."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., description="Unique case identifier, e.g. 'case-0007'")
    full_name: str = Field(..., description="Employee full name")
    email: EmailStr = Field(..., description="Personal email address")
    role: Literal[
        "software_engineer",
        "data_analyst",
        "finance_officer",
        "hr_coordinator",
        "sales_rep",
        "engineering_manager",
    ] = Field(..., description="Job role")
    level: Literal["junior", "medior", "senior", "lead"] = Field(
        ..., description="Seniority level"
    )
    department: Literal[
        "engineering", "data", "finance", "hr", "sales"
    ] = Field(..., description="Department")
    start_date: date = Field(..., description="Start date in ISO format")
    manager_email: EmailStr = Field(
        ..., description="Manager email (must be seeded manager)"
    )
    location: Literal[
        "eindhoven_office", "amsterdam_office", "remote_nl"
    ] = Field(..., description="Work location")
    contract_type: Literal[
        "permanent", "fixed_term", "contractor"
    ] = Field(..., description="Employment contract type")
    visa_required: bool = Field(
        ..., description="Whether visa/work permit required"
    )
    accessibility_needs: str | None = Field(
        None, description="Special accessibility requirements"
    )
    requested_extras: list[str] = Field(
        default_factory=list,
        description="Free-text equipment/software wishes, may be invalid",
    )


class AccessRequest(BaseModel):
    """Request for system access."""

    model_config = ConfigDict(extra="forbid")

    system: str = Field(..., description="System name, e.g. 'gitlab'")
    justification: str = Field(..., description="Why this access is needed")


class EquipmentItem(BaseModel):
    """Equipment to order."""

    model_config = ConfigDict(extra="forbid")

    catalog_id: str = Field(..., description="Catalog ID, must exist in catalog")
    name: str = Field(..., description="Equipment name")
    price_eur: float = Field(..., description="Price in EUR (fallback if catalog_id missing)")
    quantity: int = Field(default=1, description="Quantity")


class ScheduledEvent(BaseModel):
    """Scheduled onboarding event."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Event title")
    event_type: Literal[
        "it_setup",
        "manager_1on1",
        "buddy_lunch",
        "compliance_training",
        "security_training",
        "hr_intro",
    ] = Field(..., description="Type of event")
    date: date = Field(..., description="Event date")
    duration_minutes: int = Field(..., description="Duration in minutes")


class OnboardingTask(BaseModel):
    """Task in onboarding process."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Task title")
    owner: Literal[
        "hr", "it", "manager", "employee"
    ] = Field(..., description="Who owns this task")
    due_date: date = Field(..., description="When task is due")


class OnboardingPlan(BaseModel):
    """Complete onboarding plan (LLM output)."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., description="Case ID")
    employee_summary: str = Field(
        ..., description="1-2 sentence human-readable summary"
    )
    access_requests: list[AccessRequest] = Field(
        default_factory=list, description="System access requests"
    )
    equipment: list[EquipmentItem] = Field(
        default_factory=list, description="Equipment to order"
    )
    schedule: list[ScheduledEvent] = Field(
        default_factory=list, description="Scheduled events"
    )
    tasks: list[OnboardingTask] = Field(
        default_factory=list, description="Onboarding tasks"
    )
    policy_citations: list[str] = Field(
        default_factory=list,
        description="Handbook sections cited, e.g. ['§3.2', '§5.1']",
    )


class PolicyViolation(BaseModel):
    """Policy violation detected during validation."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Violation code from ViolationCode enum")
    severity: Literal["hard", "soft"] = Field(
        ..., description="hard = block; soft = self-correctable"
    )
    message: str = Field(..., description="Human-readable violation message")
    field_path: str = Field(..., description="Path to offending field, e.g. 'equipment[1].price_eur'")
    policy_ref: str = Field(
        ..., description="Policy reference, e.g. '§3.2' or 'policy_tables.yaml:budgets'"
    )


class ToolResult(BaseModel):
    """Uniform result from any tool."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(..., description="Tool name")
    ok: bool = Field(..., description="Success flag")
    data: dict | list | None = Field(
        None, description="Result data on success"
    )
    error_code: str | None = Field(None, description="Error code on failure")
    error_message: str | None = Field(None, description="Error message on failure")


class OnboardingState(BaseModel):
    """LangGraph state for onboarding workflow."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., description="Unique case ID")
    form: IntakeForm = Field(..., description="Intake form")
    plan: OnboardingPlan | None = Field(None, description="Generated onboarding plan")
    tool_results: list[ToolResult] = Field(
        default_factory=list, description="Results from tool calls"
    )
    violations: list[PolicyViolation] = Field(
        default_factory=list, description="Policy violations"
    )
    retry_count: int = Field(default=0, description="Number of revisions attempted")
    status: Literal[
        "running", "auto_approved", "escalated", "approved_by_human", "rejected_by_human", "finalized"
    ] = Field(default="running", description="Current status")
    escalation_reason: str | None = Field(
        None, description="Reason for escalation if applicable"
    )
    human_decision: Literal["approve", "reject"] | None = Field(
        None, description="Human approval decision"
    )
    human_comment: str | None = Field(None, description="Comment from human approver")
    rag_min_score: float | None = Field(
        None, description="Minimum RAG retrieval score used in plan"
    )
    audit_events: list[dict] = Field(
        default_factory=list, description="Audit trail of node executions"
    )
