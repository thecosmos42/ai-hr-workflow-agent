#!/usr/bin/env python
"""Idempotent initialization script: init database, seed data, build RAG index.

Usage:
    python scripts/init_all.py
"""
import logging
import sys
from pathlib import Path

# Add src and root to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from config.settings import get_settings
from onboard_pilot.db import init_db, get_connection, get_managers_count, get_catalog_count
from onboard_pilot.seed import seed_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Initialize all subsystems."""
    settings = get_settings()
    logger.info("Initializing onboarding system...")

    # 1. Initialize database
    logger.info(f"Initializing database at {settings.db_path}")
    init_db(settings.db_path)

    # 2. Seed reference data
    logger.info("Seeding reference data...")
    conn = get_connection(settings.db_path)
    seed_all(conn)
    conn.close()

    # 3. Verify seeding
    managers_count = get_managers_count()
    catalog_count = get_catalog_count()
    logger.info(f"Seeded {managers_count} managers, {catalog_count} catalog items")

    if managers_count != 5:
        logger.error(f"Expected 5 managers, got {managers_count}")
        return False

    if catalog_count < 20:
        logger.error(f"Expected >= 20 catalog items, got {catalog_count}")
        return False

    # 4. RAG index (placeholder for now, will be implemented in step 4)
    logger.info("RAG index initialization deferred to step 4")

    logger.info("✓ Initialization complete")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
