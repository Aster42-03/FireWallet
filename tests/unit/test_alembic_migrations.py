import os
import tempfile
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect

@pytest.mark.unit
def test_alembic_migrations_lifecycle():
    """
    Verifies that Alembic migration scripts can apply to a pristine database,
    downgrade back to base, and re-upgrade to head cleanly.
    """
    # Create temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        # Construct Alembic config pointing to backend/alembic.ini
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        ini_path = os.path.join(repo_root, "backend", "alembic.ini")
        alembic_cfg = Config(ini_path)
        
        # Override connection URL to point to temporary database with async sqlite
        async_url = f"sqlite+aiosqlite:///{tmp_db_path}"
        os.environ["DATABASE_URL"] = async_url
        alembic_cfg.set_main_option("sqlalchemy.url", async_url)

        # 1. Upgrade from empty to head
        command.upgrade(alembic_cfg, "head")

        # Verify tables and columns using standard sync sqlite inspect
        sync_url = f"sqlite:///{tmp_db_path}"
        sync_engine = create_engine(sync_url)
        inspector = inspect(sync_engine)
        tables = inspector.get_table_names()

        assert "ledger_entries" in tables
        assert "users" in tables
        assert "buckets" in tables

        columns = [col["name"] for col in inspector.get_columns("ledger_entries")]
        assert "entry_kind" in columns
        assert "counterparty_bucket" in columns
        assert "memo" in columns

        intent_cols = [col["name"] for col in inspector.get_columns("intents")]
        assert "short_tag" in intent_cols
        assert "is_emergency" in intent_cols

        coach_msg_cols = [col["name"] for col in inspector.get_columns("coach_messages")]
        assert "short_tag" in coach_msg_cols
        assert "action_card_json" in coach_msg_cols

        webhook_cols = [col["name"] for col in inspector.get_columns("paypal_webhook_events")]
        assert "status" in webhook_cols
        assert "error_message" in webhook_cols

        # 2. Downgrade to base
        command.downgrade(alembic_cfg, "base")
        inspector_post_downgrade = inspect(sync_engine)
        remaining_tables = inspector_post_downgrade.get_table_names()
        assert "ledger_entries" not in remaining_tables

        # 3. Re-upgrade to head
        command.upgrade(alembic_cfg, "head")
        inspector_reupgraded = inspect(sync_engine)
        assert "ledger_entries" in inspector_reupgraded.get_table_names()
        columns_reupgraded = [col["name"] for col in inspector_reupgraded.get_columns("ledger_entries")]
        assert "entry_kind" in columns_reupgraded

    finally:
        # Cleanup environment and temporary file
        os.environ.pop("DATABASE_URL", None)
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)
