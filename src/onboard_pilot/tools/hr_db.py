"""HR database tools for employee management."""
import sqlite3
from pathlib import Path

from onboard_pilot.schemas import IntakeForm, ToolResult


def lookup_manager(email: str, conn: sqlite3.Connection | None = None) -> ToolResult:
    """Look up a manager by email.
    
    Args:
        email: Manager email address
        conn: Optional SQLite connection (for testing)
    
    Returns:
        ToolResult with ok=True if manager exists, ok=False if not found
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email, full_name FROM employees WHERE email = ? AND is_manager = 1",
            (email,),
        )
        row = cursor.fetchone()
        if row:
            return ToolResult(
                tool="lookup_manager",
                ok=True,
                data={"email": row[0], "full_name": row[1]},
            )
        else:
            return ToolResult(
                tool="lookup_manager",
                ok=False,
                error_code="MANAGER_NOT_FOUND",
                error_message=f"Manager {email} not found",
            )
    finally:
        if should_close:
            conn.close()


def check_duplicate(email: str, conn: sqlite3.Connection | None = None) -> ToolResult:
    """Check if an employee with this email already exists.
    
    Args:
        email: Employee email address
        conn: Optional SQLite connection (for testing)
    
    Returns:
        ToolResult with ok=False and error_code='DUPLICATE_EMPLOYEE' if duplicate exists
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM employees WHERE email = ?", (email,))
        if cursor.fetchone():
            return ToolResult(
                tool="check_duplicate",
                ok=False,
                error_code="DUPLICATE_EMPLOYEE",
                error_message=f"Employee with email {email} already exists",
            )
        else:
            return ToolResult(
                tool="check_duplicate",
                ok=True,
                data={"duplicate": False},
            )
    finally:
        if should_close:
            conn.close()


def create_employee(
    form: IntakeForm, conn: sqlite3.Connection | None = None, commit: bool = True
) -> ToolResult:
    """Create a new employee record. Called only from finalize node.
    
    Args:
        form: IntakeForm with employee details
        conn: Optional SQLite connection (for testing)
        commit: Set False to leave the transaction open for the caller (finalize)
    
    Returns:
        ToolResult with ok=True if created, ok=False on errors
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM employees WHERE email = ?", (form.email,))
        existing = cursor.fetchone()
        if existing:
            # Employee already exists; idempotent success (finalize may be called twice)
            return ToolResult(
                tool="create_employee",
                ok=True,
                data={
                    "email": form.email,
                    "full_name": form.full_name,
                    "case_id": form.case_id,
                },
            )
        
        cursor.execute(
            """
            INSERT INTO employees (email, full_name, is_manager)
            VALUES (?, ?, 0)
            """,
            (form.email, form.full_name),
        )
        if commit:
            conn.commit()
        return ToolResult(
            tool="create_employee",
            ok=True,
            data={
                "email": form.email,
                "full_name": form.full_name,
                "case_id": form.case_id,
            },
        )
    except sqlite3.IntegrityError as e:
        return ToolResult(
            tool="create_employee",
            ok=False,
            error_code="DUPLICATE_EMPLOYEE",
            error_message=f"Failed to create employee: {e}",
        )
    finally:
        if should_close:
            conn.close()
