"""Violation codes and severities (plan.md §6.2, plus TOOL_FAILURE per DEVIATIONS P1)."""
from enum import Enum
from typing import Literal

from onboard_pilot.schemas import PolicyViolation

__all__ = ["PolicyViolation", "ViolationCode", "SEVERITY", "severity_of"]


class ViolationCode(str, Enum):
    """All violation codes the validators can emit."""

    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    ACCESS_NOT_IN_MATRIX = "ACCESS_NOT_IN_MATRIX"
    PRIVILEGED_ACCESS_REQUEST = "PRIVILEGED_ACCESS_REQUEST"
    TRAINING_MISSING = "TRAINING_MISSING"
    TRAINING_TOO_LATE = "TRAINING_TOO_LATE"
    MISSING_DAY1_EVENT = "MISSING_DAY1_EVENT"
    START_DATE_TOO_SOON = "START_DATE_TOO_SOON"
    MANAGER_NOT_FOUND = "MANAGER_NOT_FOUND"
    DUPLICATE_EMPLOYEE = "DUPLICATE_EMPLOYEE"
    VISA_TASK_MISSING = "VISA_TASK_MISSING"
    UNKNOWN_CATALOG_ITEM = "UNKNOWN_CATALOG_ITEM"
    ITEM_OUT_OF_STOCK = "ITEM_OUT_OF_STOCK"
    PLAN_PARSE_ERROR = "PLAN_PARSE_ERROR"
    TOOL_FAILURE = "TOOL_FAILURE"


SEVERITY: dict[ViolationCode, Literal["hard", "soft"]] = {
    ViolationCode.BUDGET_EXCEEDED: "soft",
    ViolationCode.ACCESS_NOT_IN_MATRIX: "soft",
    ViolationCode.PRIVILEGED_ACCESS_REQUEST: "hard",
    ViolationCode.TRAINING_MISSING: "soft",
    ViolationCode.TRAINING_TOO_LATE: "soft",
    ViolationCode.MISSING_DAY1_EVENT: "soft",
    ViolationCode.START_DATE_TOO_SOON: "hard",
    ViolationCode.MANAGER_NOT_FOUND: "hard",
    ViolationCode.DUPLICATE_EMPLOYEE: "hard",
    ViolationCode.VISA_TASK_MISSING: "soft",
    ViolationCode.UNKNOWN_CATALOG_ITEM: "soft",
    ViolationCode.ITEM_OUT_OF_STOCK: "soft",
    ViolationCode.PLAN_PARSE_ERROR: "soft",
    ViolationCode.TOOL_FAILURE: "soft",
}


def severity_of(code: ViolationCode) -> Literal["hard", "soft"]:
    """Return the severity for a violation code."""
    return SEVERITY[code]
