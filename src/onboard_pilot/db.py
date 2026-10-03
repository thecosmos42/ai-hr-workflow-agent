"""SQLite database helpers."""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Get SQLite connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Initialize database schema. Idempotent."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Employees table (includes managers and hired employees)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            is_manager INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Equipment catalog
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_catalog (
            id INTEGER PRIMARY KEY,
            catalog_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_eur REAL NOT NULL,
            in_stock INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Access requests (DEVIATIONS P3: status='proposed' written by it_provisioner during execute_tools)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            system TEXT NOT NULL,
            justification TEXT NOT NULL,
            status TEXT DEFAULT 'proposed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        )
    """)

    # Equipment orders (written by finalize)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_orders (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            catalog_id TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_eur REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(case_id),
            FOREIGN KEY (catalog_id) REFERENCES equipment_catalog(catalog_id)
        )
    """)

    # Onboarding tasks (written by finalize)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_tasks (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            title TEXT NOT NULL,
            owner TEXT NOT NULL,
            due_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        )
    """)

    # Calendar events (written by finalize)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            title TEXT NOT NULL,
            event_type TEXT NOT NULL,
            date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        )
    """)

    # Outbox (for mock email; written by finalize)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            to_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        )
    """)

    # Cases (control table; writable at any time; DEVIATIONS P3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'running',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finalized_at TEXT,
            escalation_reason TEXT,
            human_decision TEXT,
            human_comment TEXT
        )
    """)

    # Audit log (written at any time during execution)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            run_id TEXT,
            case_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            node TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost_eur REAL,
            latency_ms INTEGER,
            summary TEXT,
            payload_json TEXT,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized: {db_path}")


def manager_exists(email: str, conn: sqlite3.Connection | None = None) -> bool:
    """Check if manager exists in employees table."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM employees WHERE email = ? AND is_manager = 1", (email,)
        )
        return cursor.fetchone() is not None
    finally:
        if should_close:
            conn.close()


def employee_exists_by_email(email: str, conn: sqlite3.Connection | None = None) -> bool:
    """Check if employee exists by email."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM employees WHERE email = ?", (email,))
        return cursor.fetchone() is not None
    finally:
        if should_close:
            conn.close()


def get_catalog_item(catalog_id: str, conn: sqlite3.Connection | None = None) -> dict | None:
    """Get equipment catalog item by ID."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM equipment_catalog WHERE catalog_id = ?", (catalog_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def insert_employee(email: str, full_name: str, is_manager: int = 0, 
                   conn: sqlite3.Connection | None = None) -> None:
    """Insert employee. Raises if duplicate."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO employees (email, full_name, is_manager) VALUES (?, ?, ?)",
            (email, full_name, is_manager),
        )
        conn.commit()
    finally:
        if should_close:
            conn.close()


def insert_catalog_item(catalog_id: str, name: str, category: str, 
                       price_eur: float, in_stock: int = 1,
                       conn: sqlite3.Connection | None = None) -> None:
    """Insert equipment catalog item. Idempotent (ignores if exists)."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO equipment_catalog 
            (catalog_id, name, category, price_eur, in_stock)
            VALUES (?, ?, ?, ?, ?)
        """, (catalog_id, name, category, price_eur, in_stock))
        conn.commit()
    finally:
        if should_close:
            conn.close()


def get_catalog_count(conn: sqlite3.Connection | None = None) -> int:
    """Get count of items in equipment catalog."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM equipment_catalog")
        return cursor.fetchone()[0]
    finally:
        if should_close:
            conn.close()


def get_managers_count(conn: sqlite3.Connection | None = None) -> int:
    """Get count of managers."""
    should_close = False
    if conn is None:
        from config.settings import get_settings

        conn = get_connection(get_settings().db_path)
        should_close = True
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees WHERE is_manager = 1")
        return cursor.fetchone()[0]
    finally:
        if should_close:
            conn.close()
