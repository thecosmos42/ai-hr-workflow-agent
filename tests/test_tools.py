"""Unit tests for tools module. No LLM needed."""
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pytest

from onboard_pilot.db import init_db
from onboard_pilot.seed import seed_managers, seed_equipment_catalog
from onboard_pilot.schemas import IntakeForm, OnboardingPlan, ScheduledEvent, AccessRequest
from onboard_pilot.tools.equipment_catalog import get_item, search_catalog
from onboard_pilot.tools.hr_db import check_duplicate, create_employee, lookup_manager
from onboard_pilot.tools.it_provisioner import request_account
from onboard_pilot.tools.scheduler import commit_events


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        seed_managers(conn)
        seed_equipment_catalog(conn)
        conn.close()

        yield db_path


@pytest.fixture
def db_conn(temp_db):
    """Get a connection to the temp database."""
    conn = sqlite3.connect(str(temp_db))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestHrDb:
    """Tests for hr_db tools."""

    def test_lookup_manager_found(self, db_conn):
        """Test looking up an existing manager."""
        result = lookup_manager("anna.visser@corp.example", conn=db_conn)
        assert result.ok is True
        assert result.tool == "lookup_manager"
        assert result.data["email"] == "anna.visser@corp.example"
        assert result.data["full_name"] == "Anna Visser"

    def test_lookup_manager_not_found(self, db_conn):
        """Test looking up a non-existent manager."""
        result = lookup_manager("nonexistent@corp.example", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "MANAGER_NOT_FOUND"

    def test_lookup_manager_not_manager_flag(self, db_conn):
        """Test that non-managers are not returned."""
        # Insert a non-manager employee
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO employees (email, full_name, is_manager) VALUES (?, ?, 0)",
            ("regular@corp.example", "Regular Employee"),
        )
        db_conn.commit()

        result = lookup_manager("regular@corp.example", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "MANAGER_NOT_FOUND"

    def test_check_duplicate_not_duplicate(self, db_conn):
        """Test checking a new email that doesn't exist."""
        result = check_duplicate("newemp@corp.example", conn=db_conn)
        assert result.ok is True
        assert result.data["duplicate"] is False

    def test_check_duplicate_exists(self, db_conn):
        """Test checking an email that already exists."""
        # Anna is a manager, so she exists
        result = check_duplicate("anna.visser@corp.example", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "DUPLICATE_EMPLOYEE"

    def test_create_employee_success(self, db_conn):
        """Test creating a new employee."""
        form = IntakeForm(
            case_id="case-001",
            full_name="John Doe",
            email="john.doe@corp.example",
            role="software_engineer",
            level="junior",
            department="engineering",
            start_date=date(2026, 10, 15),
            manager_email="anna.visser@corp.example",
            location="eindhoven_office",
            contract_type="permanent",
            visa_required=False,
        )

        result = create_employee(form, conn=db_conn)
        assert result.ok is True
        assert result.tool == "create_employee"
        assert result.data["email"] == "john.doe@corp.example"
        assert result.data["full_name"] == "John Doe"

        # Verify inserted in DB
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE email = ?", ("john.doe@corp.example",))
        row = cursor.fetchone()
        assert row is not None
        assert row["is_manager"] == 0

    def test_create_employee_duplicate(self, db_conn):
        """Test creating employee with duplicate email."""
        form = IntakeForm(
            case_id="case-002",
            full_name="Another Anna",
            email="anna.visser@corp.example",  # Already exists as manager
            role="software_engineer",
            level="junior",
            department="engineering",
            start_date=date(2026, 10, 15),
            manager_email="anna.visser@corp.example",
            location="eindhoven_office",
            contract_type="permanent",
            visa_required=False,
        )

        result = create_employee(form, conn=db_conn)
        assert result.ok is False
        assert result.error_code == "DUPLICATE_EMPLOYEE"


class TestItProvisioner:
    """Tests for it_provisioner tools."""

    def test_request_account_success(self, db_conn):
        """Test requesting access for a valid role+system."""
        result = request_account("gitlab", "software_engineer", "case-001", conn=db_conn)
        assert result.ok is True
        assert result.tool == "request_account"
        assert result.data["system"] == "gitlab"
        assert result.data["status"] == "proposed"

        # Verify inserted in DB
        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT * FROM access_requests WHERE case_id = ? AND system = ?",
            ("case-001", "gitlab"),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "proposed"

    def test_request_account_unknown_system(self, db_conn):
        """Test requesting access for unknown system."""
        result = request_account("unknown_system", "software_engineer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "UNKNOWN_SYSTEM"

    def test_request_account_role_not_permitted(self, db_conn):
        """Test requesting access denied for role."""
        # finance_officer should not have access to gitlab
        result = request_account("gitlab", "finance_officer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "ROLE_NOT_PERMITTED"

    def test_request_account_adobe_cc_always_fails(self, db_conn):
        """Test that adobe_cc always fails for permitted roles (seeded failure)."""
        # software_engineer has adobe_cc in access matrix, but it still fails
        result = request_account("adobe_cc", "software_engineer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "LICENSE_POOL_EXHAUSTED"

    def test_request_account_adobe_cc_fails_for_permitted_role(self, db_conn):
        """Test that adobe_cc fails even when role is permitted (seeded failure)."""
        # For software_engineer who has adobe_cc in matrix
        result = request_account("adobe_cc", "software_engineer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "LICENSE_POOL_EXHAUSTED"
        
        # For finance_officer who doesn't have adobe_cc
        result = request_account("adobe_cc", "finance_officer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "ROLE_NOT_PERMITTED"

    def test_request_account_vpn_for_data_analyst(self, db_conn):
        """Test VPN access for data_analyst (allowed role)."""
        result = request_account("vpn", "data_analyst", "case-001", conn=db_conn)
        assert result.ok is True

    def test_request_account_vpn_for_finance_officer(self, db_conn):
        """Test VPN denied for finance_officer."""
        result = request_account("vpn", "finance_officer", "case-001", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "ROLE_NOT_PERMITTED"


class TestEquipmentCatalog:
    """Tests for equipment_catalog tools."""

    def test_search_catalog_by_name(self, db_conn):
        """Test searching by name substring."""
        result = search_catalog("ThinkPad", conn=db_conn)
        assert result.ok is True
        items = result.data["items"]
        assert len(items) > 0
        assert any("ThinkPad" in item["name"] for item in items)

    def test_search_catalog_by_category(self, db_conn):
        """Test searching by category."""
        result = search_catalog(category="laptop", conn=db_conn)
        assert result.ok is True
        items = result.data["items"]
        assert len(items) > 0
        assert all(item["category"] == "laptop" for item in items)

    def test_search_catalog_by_name_and_category(self, db_conn):
        """Test searching by both name and category."""
        result = search_catalog(query="Monitor", category="monitor", conn=db_conn)
        assert result.ok is True
        items = result.data["items"]
        assert len(items) > 0
        assert all(item["category"] == "monitor" for item in items)

    def test_search_catalog_no_results(self, db_conn):
        """Test search with no results."""
        result = search_catalog(query="XYZ123NonExistent", conn=db_conn)
        assert result.ok is True
        assert len(result.data["items"]) == 0

    def test_search_catalog_no_filters(self, db_conn):
        """Test search with no filters returns all items."""
        result = search_catalog(conn=db_conn)
        assert result.ok is True
        # Should have seeded 21 items
        assert result.data["count"] >= 20

    def test_get_item_found(self, db_conn):
        """Test getting an existing item."""
        result = get_item("EQ-001", conn=db_conn)
        assert result.ok is True
        assert result.data["catalog_id"] == "EQ-001"
        assert "ThinkPad" in result.data["name"]
        assert result.data["category"] == "laptop"
        assert result.data["price_eur"] == 1249

    def test_get_item_not_found(self, db_conn):
        """Test getting a non-existent item."""
        result = get_item("EQ-999", conn=db_conn)
        assert result.ok is False
        assert result.error_code == "UNKNOWN_CATALOG_ITEM"

    def test_get_item_out_of_stock(self, db_conn):
        """Test getting an out-of-stock item (should still succeed, in_stock is just data)."""
        # EQ-010 (Herman Miller Aeron Chair) should be out of stock (seeded as 0)
        result = get_item("EQ-009", conn=db_conn)
        assert result.ok is True
        assert result.data["in_stock"] == 0  # Out of stock


class TestScheduler:
    """Tests for scheduler tools."""

    def test_commit_events_empty_plan(self, db_conn):
        """Test committing an empty onboarding plan."""
        plan = OnboardingPlan(
            case_id="case-001",
            employee_summary="Test employee",
        )
        result = commit_events(plan, "case-001", "test@corp.example", conn=db_conn)
        assert result.ok is True
        assert result.data["events_committed"] == 0
        assert result.data["email_sent"] is True

        # Verify email in outbox
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM outbox WHERE case_id = ?", ("case-001",))
        row = cursor.fetchone()
        assert row is not None

    def test_commit_events_with_schedule(self, db_conn):
        """Test committing a plan with scheduled events."""
        events = [
            ScheduledEvent(
                title="IT Setup",
                event_type="it_setup",
                date=date(2026, 10, 15),
                duration_minutes=30,
            ),
            ScheduledEvent(
                title="Manager 1-on-1",
                event_type="manager_1on1",
                date=date(2026, 10, 15),
                duration_minutes=30,
            ),
        ]
        plan = OnboardingPlan(
            case_id="case-002",
            employee_summary="Manager John",
            schedule=events,
        )

        result = commit_events(plan, "case-002", "john@corp.example", conn=db_conn)
        assert result.ok is True
        assert result.data["events_committed"] == 2

        # Verify events in DB
        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM calendar_events WHERE case_id = ?", ("case-002",))
        row = cursor.fetchone()
        assert row["cnt"] == 2

    def test_commit_events_with_access_and_equipment(self, db_conn):
        """Test committing a complete plan."""
        from onboard_pilot.schemas import AccessRequest, EquipmentItem, OnboardingTask

        plan = OnboardingPlan(
            case_id="case-003",
            employee_summary="Complete onboarding",
            access_requests=[
                AccessRequest(system="gitlab", justification="Development work"),
                AccessRequest(system="slack", justification="Communication"),
            ],
            equipment=[
                EquipmentItem(
                    catalog_id="EQ-001",
                    name="ThinkPad T14",
                    price_eur=1249,
                    quantity=1,
                ),
            ],
            schedule=[
                ScheduledEvent(
                    title="IT Setup",
                    event_type="it_setup",
                    date=date(2026, 10, 15),
                    duration_minutes=30,
                ),
            ],
            tasks=[
                OnboardingTask(
                    title="Complete documentation",
                    owner="employee",
                    due_date=date(2026, 10, 22),
                ),
            ],
        )

        result = commit_events(plan, "case-003", "emp@corp.example", conn=db_conn)
        assert result.ok is True

        # Verify email was created (commit_events writes email summary)
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM outbox WHERE case_id = ?", ("case-003",))
        row = cursor.fetchone()
        assert row is not None
        assert "2 systems" in row["body"] or "2 items" in row["body"]  # Should mention access/equipment
