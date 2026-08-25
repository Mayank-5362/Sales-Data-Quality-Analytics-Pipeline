# Database configuration and connection setup
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PipelineConfig")

SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "data" / "sales_pipeline.db"))


# Build SQLite connection string
def get_connection_url() -> str:
    sqlite_file = Path(SQLITE_PATH)
    sqlite_file.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_file.as_posix()}"


# Create database engine with foreign keys enabled
def get_engine(echo: bool = False) -> Engine:
    url = get_connection_url()
    engine = create_engine(url, echo=echo)

    # Enable foreign keys in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return engine


# Test database connection
def test_db_connection(engine: Engine = None) -> bool:
    if engine is None:
        engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connection test failed: %s", exc)
        return False
