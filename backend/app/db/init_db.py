"""app/db/init_db.py — Create tables and seed catalog data."""
from __future__ import annotations

import asyncio
import logging

# ── IMPORTANT: import all models before create_all so SQLAlchemy's
# metadata is populated. Add new model modules here as phases expand.
import app.models  # noqa: F401 — registers User (and future models)

from app.db.session import Base, engine

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables. Safe to call repeatedly (CREATE IF NOT EXISTS)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")


if __name__ == "__main__":
    asyncio.run(init_db())