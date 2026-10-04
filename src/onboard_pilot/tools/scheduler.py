"""Scheduler tool for calendar and email. Mock implementation (no real APIs)."""
import sqlite3
from datetime import date

from onboard_pilot.schemas import OnboardingPlan, ToolResult


def commit_events(
    plan: OnboardingPlan, case_id: str, employee_email: str,
    conn: sqlite3.Connection | None = None, commit: bool = True
) -> ToolResult:
    """Commit scheduled events to calendar and send onboarding email.
    
    Called only from finalize node. Mock implementation:
    - Writes events to calendar_events table
    - Writes summary email to outbox table
    - No real API calls
    
    Args:
        plan: OnboardingPlan with schedule
        case_id: Case ID
        employee_email: Employee email address
        conn: Optional SQLite connection (for testing)
        commit: Set False to leave the transaction open for the caller (finalize)
    
    Returns:
        ToolResult with ok=True if committed successfully
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()

        # 1. Insert calendar events
        for event in plan.schedule:
            cursor.execute(
                """
                INSERT INTO calendar_events (case_id, title, event_type, date, duration_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    event.title,
                    event.event_type,
                    event.date.isoformat(),
                    event.duration_minutes,
                ),
            )

        # 2. Send summary email (to outbox, not real SMTP)
        email_subject = f"Onboarding Schedule: {plan.employee_summary[:50]}"
        email_body = f"""
Welcome to the team!

Your onboarding plan has been finalized. Here's what to expect:

Employee Summary: {plan.employee_summary}

Scheduled Events: {len(plan.schedule)} events
- {', '.join(e.title for e in plan.schedule[:5])}
{'...' if len(plan.schedule) > 5 else ''}

System Access: {len(plan.access_requests)} systems
- {', '.join(a.system for a in plan.access_requests[:5])}
{'...' if len(plan.access_requests) > 5 else ''}

Equipment: {len(plan.equipment)} items
- {', '.join(f"{e.name} x{e.quantity}" for e in plan.equipment[:5])}
{'...' if len(plan.equipment) > 5 else ''}

Please confirm receipt of this email.
"""

        cursor.execute(
            """
            INSERT INTO outbox (case_id, to_email, subject, body)
            VALUES (?, ?, ?, ?)
            """,
            (case_id, employee_email, email_subject, email_body),
        )

        if commit:
            conn.commit()

        return ToolResult(
            tool="commit_events",
            ok=True,
            data={
                "case_id": case_id,
                "events_committed": len(plan.schedule),
                "email_sent": True,
                "email_to": employee_email,
            },
        )
    except Exception as e:
        return ToolResult(
            tool="commit_events",
            ok=False,
            error_code="SCHEDULER_ERROR",
            error_message=f"Failed to commit events: {e}",
        )
    finally:
        if should_close:
            conn.close()
