"""
Unit Tests for Data Transformation and Cleaning Module
"""

import pytest
import pandas as pd
from src.transform import (
    standardize_text,
    clean_and_coerce_types,
    handle_missing_and_imputations,
    derive_features,
    clean,
)


def test_standardize_text():
    df = pd.DataFrame([
        {"customer_name": "  acme corp  ", "region": "  nOrTh  ", "category": "  eLeCtRoNiCs  "},
        {"customer_name": "GLOBAL TECH", "region": "apac", "category": "SOFTWARE"},
    ])
    df_std, count = standardize_text(df)

    assert df_std.loc[0, "customer_name"] == "Acme Corp"
    assert df_std.loc[0, "region"] == "North"
    assert df_std.loc[0, "category"] == "Electronics"
    assert df_std.loc[1, "region"] == "APAC"
    assert count > 0


def test_clean_and_coerce_types():
    df = pd.DataFrame([
        {"sales_amount": "$1,250.50", "quantity": " 4 ", "customer_id": " 101 ", "sale_date": "2024-01-15"},
    ])
    df_typed = clean_and_coerce_types(df)

    assert df_typed.loc[0, "sales_amount"] == 1250.50
    assert df_typed.loc[0, "quantity"] == 4
    assert df_typed.loc[0, "customer_id"] == 101
    assert str(df_typed.loc[0, "sale_date"]) == "2024-01-15"


def test_handle_missing_and_imputations():
    df = pd.DataFrame([
        {"customer_id": 101, "customer_name": "", "region": "", "product_id": 201, "product_name": "", "category": ""},
    ])
    df_imp, count = handle_missing_and_imputations(df)

    assert df_imp.loc[0, "region"] == "Unknown"
    assert df_imp.loc[0, "category"] == "General"
    assert "Customer 101" in df_imp.loc[0, "customer_name"]
    assert "Product 201" in df_imp.loc[0, "product_name"]
    assert count >= 4


def test_derive_features():
    df = pd.DataFrame([
        {"sales_amount": 1500.00, "quantity": 3, "sale_date": "2024-03-20"},
    ])
    df_feat = derive_features(df)

    assert df_feat.loc[0, "unit_price"] == 500.00
    assert df_feat.loc[0, "year_month"] == "2024-03"


def test_full_clean_workflow(sample_dirty_df):
    clean_df, quarantine_df, stats = clean(sample_dirty_df)

    assert len(clean_df) > 0
    assert len(quarantine_df) > 0
    assert stats["duplicates_removed"] == 1
    assert stats["quarantined_rows"] == len(quarantine_df)
    assert "_rejection_reasons" in quarantine_df.columns
    assert "unit_price" in clean_df.columns
    assert "year_month" in clean_df.columns
