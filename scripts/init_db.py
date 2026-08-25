# Database table initialization script
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from src.config import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DBInitializer")


# Apply schema DDL statements to database
def init_database(schema_path: Path = None):
    if schema_path is None:
        schema_path = BASE_DIR / "sql" / "schema.sql"

    if not schema_path.exists():
        sys.exit(1)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    engine = get_engine()
    statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]

    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                logger.warning("Statement notice: %s", exc)

        # Add source_file column if not present
        try:
            sales_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(sales)")).fetchall()]
            if "source_file" not in sales_cols:
                conn.execute(text("ALTER TABLE sales ADD COLUMN source_file TEXT DEFAULT 'manual'"))
        except Exception as exc:
            logger.debug("Migration notice: %s", exc)

    logger.info("[SUCCESS] SQLite database initialization completed successfully!")


if __name__ == "__main__":
    init_database()
