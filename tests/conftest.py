"""
Pytest Fixtures and Test Configurations
"""

import pytest
import pandas as pd
from sqlalchemy import create_engine, text
from src.config import BASE_DIR
from scripts.init_db import init_database


@pytest.fixture(scope="session")
def test_engine():
    """
    Creates an isolated in-memory or file-based SQLite database engine for testing.
    """
    engine = create_engine("sqlite:///:memory:")
    
    # Initialize schema
    schema_path = BASE_DIR / "sql" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            sql_to_run = stmt
            sql_to_run = sql_to_run.replace("INT PRIMARY KEY AUTO_INCREMENT", "INTEGER PRIMARY KEY AUTOINCREMENT")
            sql_to_run = sql_to_run.replace("AUTO_INCREMENT", "")
            sql_to_run = sql_to_run.replace("DECIMAL(12,2)", "NUMERIC")
            sql_to_run = sql_to_run.replace("DATETIME DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            try:
                conn.execute(text(sql_to_run))
            except Exception:
                pass

    return engine


@pytest.fixture
def sample_clean_df():
    """
    Returns a clean synthetic sales DataFrame.
    """
    return pd.DataFrame([
        {
            "customer_id": 101,
            "customer_name": "Acme Corporation",
            "region": "North",
            "product_id": 201,
            "product_name": "Cloud Server",
            "category": "Hardware",
            "sale_date": "2024-01-15",
            "quantity": 2,
            "sales_amount": 3000.00
        },
        {
            "customer_id": 102,
            "customer_name": "Global Tech",
            "region": "South",
            "product_id": 202,
            "product_name": "SaaS Platform",
            "category": "Software",
            "sale_date": "2024-01-16",
            "quantity": 5,
            "sales_amount": 1750.00
        }
    ])


@pytest.fixture
def sample_dirty_df():
    """
    Returns a dirty DataFrame with multiple edge case errors.
    """
    return pd.DataFrame([
        # Clean row
        {"customer_id": "101", "customer_name": "Acme Corp", "region": "North", "product_id": "201", "product_name": "Cloud Server", "category": "Hardware", "sale_date": "2024-01-10", "quantity": "2", "sales_amount": "2000.00"},
        # Duplicate of above
        {"customer_id": "101", "customer_name": "Acme Corp", "region": "North", "product_id": "201", "product_name": "Cloud Server", "category": "Hardware", "sale_date": "2024-01-10", "quantity": "2", "sales_amount": "2000.00"},
        # Whitespace and weird casing
        {"customer_id": " 102 ", "customer_name": "  global tech  ", "region": " sOuTh ", "product_id": " 202 ", "product_name": " saas platform ", "category": " softWARE ", "sale_date": "2024-01-11", "quantity": "3", "sales_amount": "$1,050.00"},
        # Missing non-critical fields
        {"customer_id": "103", "customer_name": "", "region": "", "product_id": "203", "product_name": "", "category": "", "sale_date": "2024-01-12", "quantity": "1", "sales_amount": "400.00"},
        # Fatal: negative sales amount
        {"customer_id": "104", "customer_name": "Apex", "region": "East", "product_id": "204", "product_name": "Security", "category": "Software", "sale_date": "2024-01-13", "quantity": "1", "sales_amount": "-500.00"},
        # Fatal: zero quantity
        {"customer_id": "105", "customer_name": "Vanguard", "region": "West", "product_id": "205", "product_name": "Video", "category": "Hardware", "sale_date": "2024-01-14", "quantity": "0", "sales_amount": "900.00"},
        # Fatal: unparseable date
        {"customer_id": "106", "customer_name": "Pinnacle", "region": "EMEA", "product_id": "206", "product_name": "Database", "category": "Cloud", "sale_date": "bad-date-format", "quantity": "1", "sales_amount": "1200.00"},
        # Fatal: missing customer_id
        {"customer_id": "", "customer_name": "Anonymous", "region": "North", "product_id": "201", "product_name": "Cloud Server", "category": "Hardware", "sale_date": "2024-01-15", "quantity": "1", "sales_amount": "1000.00"},
    ])
