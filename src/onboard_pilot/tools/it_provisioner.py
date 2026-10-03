"""IT provisioning tools for system access management.

Note: Tool-level access matrix check duplicates validator logic intentionally.
Real API would reject invalid access; validator is the policy backstop.
"""
import sqlite3

from onboard_pilot.schemas import ToolResult


def _load_access_matrix() -> tuple[dict, list]:
    """Load access matrix and privileged systems from policy_tables.yaml."""
    from config.settings import load_policy_tables

    policy = load_policy_tables()
    return policy["access_matrix"], policy["privileged_systems"]


def request_account(
    system: str, role: str, case_id: str, conn: sqlite3.Connection | None = None
) -> ToolResult:
    """Request system access for an employee.
    
    Behavior (order FIXED):
    1. If system not in access matrix at all → UNKNOWN_SYSTEM
    2. If system not allowed for role → ROLE_NOT_PERMITTED
    3. If system is adobe_cc → always LICENSE_POOL_EXHAUSTED (seeded failure)
    4. Otherwise → ok, INSERT access_requests row with status='proposed'
    
    Args:
        system: System name (e.g. 'gitlab')
        role: Employee role
        case_id: Case ID for tracking
        conn: Optional SQLite connection (for testing)
    
    Returns:
        ToolResult with ok=True (access request created) or ok=False with error code
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    access_matrix, privileged_systems = _load_access_matrix()

    # 1. Check if system exists in access matrix at all
    systems_in_matrix = set()
    for role_systems in access_matrix.values():
        systems_in_matrix.update(role_systems)
    if system not in systems_in_matrix and system not in privileged_systems:
        return ToolResult(
            tool="request_account",
            ok=False,
            error_code="UNKNOWN_SYSTEM",
            error_message=f"System '{system}' not in access matrix",
        )

    # 2. Check if system allowed for this role
    if system not in access_matrix.get(role, []):
        return ToolResult(
            tool="request_account",
            ok=False,
            error_code="ROLE_NOT_PERMITTED",
            error_message=f"Role '{role}' not permitted for system '{system}'",
        )

    # 3. Seeded failure: adobe_cc always fails (deterministic)
    if system == "adobe_cc":
        return ToolResult(
            tool="request_account",
            ok=False,
            error_code="LICENSE_POOL_EXHAUSTED",
            error_message="Adobe Creative Cloud license pool exhausted",
        )

    # 4. Success: INSERT access_requests row with status='proposed'
    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO access_requests (case_id, system, justification, status)
            VALUES (?, ?, ?, 'proposed')
            """,
            (case_id, system, f"Access to {system} required for role {role}"),
        )
        conn.commit()
        return ToolResult(
            tool="request_account",
            ok=True,
            data={
                "system": system,
                "status": "proposed",
                "case_id": case_id,
            },
        )
    finally:
        if should_close:
            conn.close()


def get_connection(db_path):
    """Get SQLite connection."""
    from onboard_pilot.db import get_connection as db_get_connection

    return db_get_connection(db_path)
