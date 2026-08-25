"""
Unit Tests for Data Quality Validation Rules
"""

import pytest
import pandas as pd
from datetime import date
from src.validate import (
    ValidationReport,
    check_missing_values,
    check_duplicates,
    check_numeric_ranges,
    check_date_validity,
    check_orphan_references,
    check_data_types,
    run_checks,
)


def test_check_missing_values():
    df = pd.DataFrame([
        {"customer_id": "101", "product_id": "201", "sale_date": "2024-01-01", "quantity": "1", "sales_amount": "100.00"},
        {"customer_id": "", "product_id": "202", "sale_date": "2024-01-02", "quantity": "2", "sales_amount": "200.00"},
        {"customer_id": "103", "product_id": None, "sale_date": "2024-01-03", "quantity": "3", "sales_amount": "300.00"},
    ])
    report = ValidationReport(len(df))
    check_missing_values(df, report)

    assert report.missing_counts["customer_id"] == 1
    assert report.missing_counts["product_id"] == 1
    assert len(report.fatal_row_indices) == 2


def test_check_duplicates():
    df = pd.DataFrame([
        {"customer_id": "101", "product_id": "201", "sale_date": "2024-01-01", "quantity": "1", "sales_amount": "100.00"},
        {"customer_id": "101", "product_id": "201", "sale_date": "2024-01-01", "quantity": "1", "sales_amount": "100.00"},
        {"customer_id": "102", "product_id": "202", "sale_date": "2024-01-02", "quantity": "2", "sales_amount": "200.00"},
    ])
    report = ValidationReport(len(df))
    check_duplicates(df, report)

    assert report.duplicate_count == 1


def test_check_numeric_ranges():
    df = pd.DataFrame([
        {"customer_id": "101", "product_id": "201", "quantity": "5", "sales_amount": "500.00"},
        {"customer_id": "102", "product_id": "202", "quantity": "0", "sales_amount": "200.00"},   # Zero qty
        {"customer_id": "103", "product_id": "203", "quantity": "-3", "sales_amount": "300.00"},  # Negative qty
        {"customer_id": "104", "product_id": "204", "quantity": "2", "sales_amount": "-150.00"},  # Negative sales
        {"customer_id": "105", "product_id": "205", "quantity": "1", "sales_amount": "$250.00"},  # Currency string
    ])
    report = ValidationReport(len(df))
    check_numeric_ranges(df, report)

    assert report.negative_or_zero_qty == 2
    assert report.negative_or_zero_sales == 1
    assert 1 in report.fatal_row_indices
    assert 2 in report.fatal_row_indices
    assert 3 in report.fatal_row_indices


def test_check_date_validity():
    df = pd.DataFrame([
        {"sale_date": "2024-01-15"},
        {"sale_date": "invalid-date-string"},
        {"sale_date": "2099-12-31"},
        {"sale_date": "1985-05-20"},  # Year < 2000
    ])
    report = ValidationReport(len(df))
    check_date_validity(df, report, max_future_date=date(2025, 1, 1))

    assert report.invalid_dates == 2  # unparseable + pre-2000
    assert report.future_dates == 1
    assert len(report.fatal_row_indices) == 3


def test_check_orphan_references():
    df = pd.DataFrame([
        {"customer_id": "101", "product_id": "201"},
        {"customer_id": "-5", "product_id": "202"},   # Negative ID
        {"customer_id": "999", "product_id": "203"},  # Orphan not in master
    ])
    report = ValidationReport(len(df))
    check_orphan_references(
        df,
        report,
        valid_customer_ids={101, 102},
        valid_product_ids={201, 202, 203}
    )

    assert report.orphan_customers >= 2
    assert 1 in report.fatal_row_indices
    assert 2 in report.fatal_row_indices


def test_check_data_types():
    df = pd.DataFrame([
        {"sales_amount": "1250.50", "quantity": "4"},
        {"sales_amount": "ABC_NOT_NUMERIC", "quantity": "2"},
        {"sales_amount": "500.00", "quantity": "THREE"},
    ])
    report = ValidationReport(len(df))
    check_data_types(df, report)

    assert report.dtype_errors["sales_amount"] == 1
    assert report.dtype_errors["quantity"] == 1
    assert 1 in report.fatal_row_indices
    assert 2 in report.fatal_row_indices


def test_full_run_checks(sample_dirty_df):
    report = run_checks(sample_dirty_df, max_future_date=date(2025, 1, 1))
    summary = report.to_dict()

    assert summary["total_records"] == 8
    assert summary["duplicate_records"] == 1
    assert summary["invalid_records"] >= 4
    assert summary["valid_records"] <= 4
