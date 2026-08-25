# Database loading, idempotency tracking, and archiving module
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from src.config import get_engine

logger = logging.getLogger("DataLoader")


# Upsert unique customer records into customers table
def upsert_customers(df: pd.DataFrame, engine: Engine) -> int:
    if "customer_id" not in df.columns or df.empty:
        return 0

    if "customer_name" not in df.columns and "region" not in df.columns:
        return 0

    cust_cols = ["customer_id"]
    if "customer_name" in df.columns:
        cust_cols.append("customer_name")
    if "region" in df.columns:
        cust_cols.append("region")

    unique_custs = df[cust_cols].drop_duplicates(subset=["customer_id"]).copy()
    if "customer_name" not in unique_custs.columns:
        unique_custs["customer_name"] = "Unknown Customer"
    if "region" not in unique_custs.columns:
        unique_custs["region"] = "Unknown"

    unique_custs["customer_id"] = unique_custs["customer_id"].astype(int)
    records = unique_custs.to_dict(orient="records")

    with engine.begin() as conn:
        for row in records:
            stmt = text("""
                INSERT INTO customers (customer_id, customer_name, region)
                VALUES (:customer_id, :customer_name, :region)
                ON CONFLICT(customer_id) DO UPDATE SET
                    customer_name = excluded.customer_name,
                    region = excluded.region
            """)
            conn.execute(stmt, row)

    return len(records)


# Upsert unique product records into products table
def upsert_products(df: pd.DataFrame, engine: Engine) -> int:
    if "product_id" not in df.columns or df.empty:
        return 0

    if "product_name" not in df.columns and "category" not in df.columns:
        return 0

    prod_cols = ["product_id"]
    if "product_name" in df.columns:
        prod_cols.append("product_name")
    if "category" in df.columns:
        prod_cols.append("category")

    unique_prods = df[prod_cols].drop_duplicates(subset=["product_id"]).copy()
    if "product_name" not in unique_prods.columns:
        unique_prods["product_name"] = "Unknown Product"
    if "category" not in unique_prods.columns:
        unique_prods["category"] = "General"

    unique_prods["product_id"] = unique_prods["product_id"].astype(int)
    records = unique_prods.to_dict(orient="records")

    with engine.begin() as conn:
        for row in records:
            stmt = text("""
                INSERT INTO products (product_id, product_name, category)
                VALUES (:product_id, :product_name, :category)
                ON CONFLICT(product_id) DO UPDATE SET
                    product_name = excluded.product_name,
                    category = excluded.category
            """)
            conn.execute(stmt, row)

    return len(records)


# Insert sales transactions into sales table
def insert_sales(df: pd.DataFrame, source_file: str, engine: Engine) -> int:
    if df.empty:
        return 0

    sales_cols = ["customer_id", "product_id", "sale_date", "quantity", "sales_amount"]
    if not all(col in df.columns for col in sales_cols):
        return 0

    sales_df = df[sales_cols].copy()
    sales_df["customer_id"] = sales_df["customer_id"].astype(int)
    sales_df["product_id"] = sales_df["product_id"].astype(int)
    sales_df["quantity"] = sales_df["quantity"].astype(int)
    sales_df["sales_amount"] = sales_df["sales_amount"].astype(float)
    sales_df["sale_date"] = pd.to_datetime(sales_df["sale_date"]).dt.strftime("%Y-%m-%d")
    sales_df["source_file"] = source_file

    # Remove previous rows for this source file to avoid duplication
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(sales)")).fetchall()]
        if "source_file" not in cols:
            conn.execute(text("ALTER TABLE sales ADD COLUMN source_file TEXT DEFAULT 'manual'"))
        conn.execute(text("DELETE FROM sales WHERE source_file = :src"), {"src": source_file})

    sales_df.to_sql(name="sales", con=engine, if_exists="append", index=False, chunksize=1000, method="multi")
    return len(sales_df)


# Insert audit entry into data_quality_log table
def log_data_quality(file_name: str, stats: Dict[str, Any], engine: Engine, status: str = "SUCCESS") -> int:
    with engine.begin() as conn:
        stmt = text("""
            INSERT INTO data_quality_log (
                run_date, file_name, records_read, duplicates_removed,
                missing_fixed, invalid_rows, records_loaded, status
            ) VALUES (
                :run_date, :file_name, :records_read, :duplicates_removed,
                :missing_fixed, :invalid_rows, :records_loaded, :status
            )
        """)
        params = {
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": file_name,
            "records_read": stats.get("initial_rows", 0),
            "duplicates_removed": stats.get("duplicates_removed", 0),
            "missing_fixed": stats.get("missing_fixed", 0),
            "invalid_rows": stats.get("quarantined_rows", 0),
            "records_loaded": stats.get("records_loaded", 0),
            "status": status,
        }
        conn.execute(stmt, params)

    return 1


# Save processed and quarantined CSV files to disk
def archive_data(
    clean_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
    source_filename: str,
    output_dir: str = "data"
) -> Dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(source_filename).stem

    processed_dir = Path(output_dir) / "processed"
    quarantine_dir = Path(output_dir) / "quarantine"
    processed_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    paths = {}
    if not clean_df.empty:
        proc_file = processed_dir / f"{base_name}_clean_{timestamp}.csv"
        clean_df.to_csv(proc_file, index=False)
        paths["processed"] = str(proc_file)

    if not quarantine_df.empty:
        quar_file = quarantine_dir / f"{base_name}_quarantine_{timestamp}.csv"
        quarantine_df.to_csv(quar_file, index=False)
        paths["quarantine"] = str(quar_file)

    return paths


# Check if file SHA256 was already processed
def is_file_already_processed(file_hash: str, engine: Engine) -> bool:
    if not file_hash:
        return False
    try:
        with engine.connect() as conn:
            stmt = text("SELECT 1 FROM processed_files WHERE file_hash = :hash")
            res = conn.execute(stmt, {"hash": file_hash}).first()
            return res is not None
    except Exception as exc:
        logger.debug("Notice checking processed_files: %s", exc)
        return False


# Record file SHA256 hash in processed_files table
def mark_file_processed(file_hash: str, file_name: str, row_count: int, engine: Engine) -> None:
    if not file_hash:
        return
    try:
        with engine.begin() as conn:
            stmt = text("""
                INSERT INTO processed_files (file_hash, file_name, row_count)
                VALUES (:file_hash, :file_name, :row_count)
                ON CONFLICT(file_hash) DO UPDATE SET
                    row_count = excluded.row_count,
                    loaded_at = CURRENT_TIMESTAMP
            """)
            conn.execute(stmt, {"file_hash": file_hash, "file_name": file_name, "row_count": row_count})
    except Exception as exc:
        logger.debug("Notice marking processed_files: %s", exc)


# Main database loader function
def load_to_database(
    clean_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
    stats: Dict[str, Any],
    file_name: str,
    engine: Optional[Engine] = None,
    file_hash: Optional[str] = None
) -> Dict[str, Any]:
    if engine is None:
        engine = get_engine()

    # 1. Upsert dimensions
    upsert_customers(clean_df, engine)
    upsert_products(clean_df, engine)

    # 2. Insert sales facts
    records_loaded = insert_sales(clean_df, file_name, engine)
    stats["records_loaded"] = records_loaded

    # 3. Log audit entry and file hash
    log_data_quality(file_name, stats, engine, status="SUCCESS")
    if file_hash:
        mark_file_processed(file_hash, file_name, records_loaded, engine)

    # 4. Save archive CSVs
    archive_paths = archive_data(clean_df, quarantine_df, file_name)

    return {
        "records_loaded": records_loaded,
        "archive_paths": archive_paths,
        "status": "SUCCESS"
    }
