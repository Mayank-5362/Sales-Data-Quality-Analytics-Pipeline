"""
End-to-End Pipeline Integration Tests
"""

import pytest
import pandas as pd
from sqlalchemy import text
from src import extract, validate, transform, load, report


def test_full_pipeline_integration(test_engine, sample_dirty_df, tmp_path):
    # 1. Save dirty dataframe to temporary CSV
    csv_path = tmp_path / "test_dirty_sales.csv"
    sample_dirty_df.to_csv(csv_path, index=False)

    # 2. Extract
    extracted_df, metadata = extract.read_csv_file(csv_path)
    assert len(extracted_df) == len(sample_dirty_df)
    assert metadata["file_name"] == "test_dirty_sales.csv"

    # 3. Validate
    val_report = validate.run_checks(extracted_df, engine=test_engine)
    assert val_report.total_rows == len(sample_dirty_df)

    # 4. Transform
    clean_df, quarantine_df, stats = transform.clean(extracted_df, val_report, engine=test_engine)
    assert len(clean_df) > 0
    assert len(quarantine_df) > 0

    # 5. Load to test database
    load_result = load.load_to_database(
        clean_df=clean_df,
        quarantine_df=quarantine_df,
        stats=stats,
        file_name="test_dirty_sales.csv",
        engine=test_engine,
        file_hash="testhash123"
    )

    assert load_result["status"] == "SUCCESS"
    assert load_result["records_loaded"] == len(clean_df)

    # Verify rows in database
    with test_engine.connect() as conn:
        sales_count = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar()
        assert sales_count == len(clean_df)

        cust_count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        assert cust_count > 0

        prod_count = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        assert prod_count > 0

        log_count = conn.execute(text("SELECT COUNT(*) FROM data_quality_log")).scalar()
        assert log_count >= 1

    # 6. Report Generation
    report_res = report.generate(engine=test_engine, reports_dir=str(tmp_path / "reports"))
    assert report_res["kpis"]["total_orders"] == len(clean_df)
    assert report_res["kpis"]["total_revenue"] > 0


def test_orphan_foreign_key_quarantine(test_engine):
    # Setup clean customers and products
    with test_engine.begin() as conn:
        conn.execute(text("INSERT OR REPLACE INTO customers (customer_id, customer_name, region) VALUES (101, 'Valid Cust', 'North')"))
        conn.execute(text("INSERT OR REPLACE INTO products (product_id, product_name, category) VALUES (201, 'Valid Prod', 'Tech')"))

    sales_df = pd.DataFrame([
        {"customer_id": 101, "product_id": 201, "sale_date": "2024-01-10", "quantity": 1, "sales_amount": 100.0}, # Valid
        {"customer_id": 999, "product_id": 201, "sale_date": "2024-01-11", "quantity": 1, "sales_amount": 100.0}, # Orphan Customer
        {"customer_id": 101, "product_id": 999, "sale_date": "2024-01-12", "quantity": 1, "sales_amount": 100.0}, # Orphan Product
    ])

    val_report = validate.run_checks(sales_df, engine=test_engine)
    clean_df, quarantine_df, stats = transform.clean(sales_df, val_report, engine=test_engine)

    assert len(clean_df) == 1
    assert len(quarantine_df) == 2
    assert stats["quarantined_rows"] == 2


def test_idempotency_file_rerun(test_engine, tmp_path):
    csv_path = tmp_path / "idempotent_test.csv"
    pd.DataFrame([
        {"customer_id": 101, "customer_name": "Cust A", "region": "East", "product_id": 201, "product_name": "Prod A", "category": "General", "sale_date": "2024-02-01", "quantity": 1, "sales_amount": 50.0}
    ]).to_csv(csv_path, index=False)

    from main import run_pipeline_for_file
    res1 = run_pipeline_for_file(csv_path, engine=test_engine)
    assert res1["status"] == "SUCCESS"

    # Second run should skip and NOT duplicate
    res2 = run_pipeline_for_file(csv_path, engine=test_engine)
    assert res2["status"] == "ALREADY_PROCESSED"

    with test_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM sales WHERE source_file = 'idempotent_test.csv'")).scalar()
        assert count == 1
