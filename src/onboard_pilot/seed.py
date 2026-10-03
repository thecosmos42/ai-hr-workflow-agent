"""Seed reference data into database."""
import logging
import sqlite3

logger = logging.getLogger(__name__)


def seed_managers(conn: sqlite3.Connection) -> None:
    """Seed 5 seeded managers. Idempotent."""
    managers = [
        ("anna.visser@corp.example", "Anna Visser"),
        ("tom.bakker@corp.example", "Tom Bakker"),
        ("sofia.jansen@corp.example", "Sofia Jansen"),
        ("mark.devries@corp.example", "Mark de Vries"),
        ("lisa.smit@corp.example", "Lisa Smit"),
    ]
    cursor = conn.cursor()
    for email, name in managers:
        cursor.execute("""
            INSERT OR IGNORE INTO employees (email, full_name, is_manager)
            VALUES (?, ?, 1)
        """, (email, name))
    conn.commit()
    logger.info(f"Seeded {len(managers)} managers")


def seed_equipment_catalog(conn: sqlite3.Connection) -> None:
    """Seed ~20 equipment items. Idempotent."""
    items = [
        # Laptops
        ("EQ-001", "ThinkPad T14", "laptop", 1249, 1),
        ("EQ-002", "MacBook Pro 14", "laptop", 3499, 1),
        ("EQ-003", "MacBook Air 13", "laptop", 1399, 1),
        ("EQ-004", "Dell XPS 13", "laptop", 1199, 1),
        # Monitors
        ("EQ-005", "Dell 27\" Monitor", "monitor", 289, 1),
        ("EQ-006", "LG 34\" Ultrawide", "monitor", 549, 1),
        ("EQ-007", "LG 27\" 4K", "monitor", 449, 1),
        ("EQ-008", "ASUS 24\" Monitor", "monitor", 199, 1),
        # Furniture
        ("EQ-009", "Herman Miller Aeron Chair", "furniture", 1100, 0),
        ("EQ-010", "Steelcase Leap Chair", "furniture", 850, 1),
        ("EQ-011", "IKEA Bekant Desk", "furniture", 250, 1),
        # Peripherals
        ("EQ-012", "Logitech MX Master 3", "peripheral", 99, 1),
        ("EQ-013", "Apple Magic Mouse", "peripheral", 79, 1),
        ("EQ-014", "Keychron K8 Keyboard", "peripheral", 89, 1),
        ("EQ-015", "Apple Magic Keyboard", "peripheral", 129, 1),
        ("EQ-016", "Bose QC45 Headphones", "peripheral", 379, 1),
        ("EQ-017", "Sony WH-1000XM5", "peripheral", 399, 1),
        ("EQ-018", "Logitech C920 Webcam", "peripheral", 89, 1),
        ("EQ-019", "Jabra Evolve 75", "peripheral", 189, 1),
        ("EQ-020", "CalDigit Thunderbolt Dock", "peripheral", 349, 1),
        ("EQ-021", "Belkin USB-C Multiport", "peripheral", 129, 1),
    ]
    cursor = conn.cursor()
    for catalog_id, name, category, price, in_stock in items:
        cursor.execute("""
            INSERT OR IGNORE INTO equipment_catalog 
            (catalog_id, name, category, price_eur, in_stock)
            VALUES (?, ?, ?, ?, ?)
        """, (catalog_id, name, category, price, in_stock))
    conn.commit()
    logger.info(f"Seeded {len(items)} equipment items")


def seed_all(conn: sqlite3.Connection) -> None:
    """Seed all reference data. Idempotent."""
    seed_managers(conn)
    seed_equipment_catalog(conn)
