from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from db import engine


ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_creates_user_foundation_tables():
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    tables = inspect(engine()).get_table_names()
    assert {
        "users",
        "sessions",
        "watchlist_items",
        "portfolio_holdings",
        "closed_positions",
        "user_reports",
        "research_notes",
        "user_ai_credentials",
        "ai_usage_events",
    }.issubset(tables)
