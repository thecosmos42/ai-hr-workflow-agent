"""Equipment catalog tool for browsing available equipment.

Note: This tool does NOT enforce budget constraints. Budget validation is
done by the validators module to maintain separation of concerns: tools
simulate external systems (catalog/inventory), validators enforce policy.
"""
import sqlite3

from onboard_pilot.schemas import ToolResult


def search_catalog(
    query: str | None = None,
    category: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> ToolResult:
    """Search equipment catalog by name or category.
    
    Args:
        query: Search string to match against name (case-insensitive)
        category: Filter by category (e.g. 'laptop', 'monitor')
        conn: Optional SQLite connection (for testing)
    
    Returns:
        ToolResult with list of matching items {catalog_id, name, category, price_eur, in_stock}
    """
    from config.settings import get_settings
    from onboard_pilot.db import get_connection

    should_close = False
    if conn is None:
        conn = get_connection(get_settings().db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        sql = "SELECT catalog_id, name, category, price_eur, in_stock FROM equipment_catalog WHERE 1=1"
        params = []

        if query:
            sql += " AND name LIKE ?"
            params.append(f"%{query}%")

        if category:
            sql += " AND category = ?"
            params.append(category)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        items = [
            {
                "catalog_id": row[0],
                "name": row[1],
                "category": row[2],
                "price_eur": row[3],
                "in_stock": row[4],
            }
            for row in rows
        ]

        return ToolResult(
            tool="search_catalog",
            ok=True,
            data={"items": items, "count": len(items)},
        )
    finally:
        if should_close:
            conn.close()


def get_item(
    catalog_id: str, conn: sqlite3.Connection | None = None
) -> ToolResult:
    """Get a single equipment item by catalog ID.
    
    Args:
        catalog_id: Equipment catalog ID (e.g. 'EQ-001')
        conn: Optional SQLite connection (for testing)
    
    Returns:
        ToolResult with item details or UNKNOWN_CATALOG_ITEM error
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
            "SELECT catalog_id, name, category, price_eur, in_stock FROM equipment_catalog WHERE catalog_id = ?",
            (catalog_id,),
        )
        row = cursor.fetchone()

        if not row:
            return ToolResult(
                tool="get_item",
                ok=False,
                error_code="UNKNOWN_CATALOG_ITEM",
                error_message=f"Catalog item '{catalog_id}' not found",
            )

        return ToolResult(
            tool="get_item",
            ok=True,
            data={
                "catalog_id": row[0],
                "name": row[1],
                "category": row[2],
                "price_eur": row[3],
                "in_stock": row[4],
            },
        )
    finally:
        if should_close:
            conn.close()
