# Data quality validation module
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Set
import pandas as pd
import numpy as np

logger = logging.getLogger("DataValidator")


# Data quality report class
class ValidationReport:
    def __init__(self, total_rows: int):
        self.total_rows = total_rows
        self.missing_counts: Dict[str, int] = {}
        self.duplicate_count: int = 0
        self.negative_or_zero_sales: int = 0
        self.negative_or_zero_qty: int = 0
        self.invalid_dates: int = 0
        self.future_dates: int = 0
        self.orphan_customers: int = 0
        self.orphan_products: int = 0
        self.dtype_errors: Dict[str, int] = {}
        self.fatal_row_indices: Set[int] = set()
        self.row_level_issues: Dict[int, List[str]] = {}

    def add_issue(self, row_idx: int, issue_msg: str, is_fatal: bool = True):
        if row_idx not in self.row_level_issues:
            self.row_level_issues[row_idx] = []
        self.row_level_issues[row_idx].append(issue_msg)
        if is_fatal:
            self.fatal_row_indices.add(row_idx)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_rows,
            "valid_records": self.total_rows - len(self.fatal_row_indices),
            "invalid_records": len(self.fatal_row_indices),
            "duplicate_records": self.duplicate_count,
            "missing_values_by_column": self.missing_counts,
            "negative_or_zero_sales": self.negative_or_zero_sales,
            "negative_or_zero_quantity": self.negative_or_zero_qty,
            "invalid_dates": self.invalid_dates,
            "future_dates": self.future_dates,
            "orphan_customers": self.orphan_customers,
            "orphan_products": self.orphan_products,
            "dtype_errors": self.dtype_errors,
        }


# Check 1: Find missing values in required columns
def check_missing_values(df: pd.DataFrame, report: ValidationReport) -> None:
    for col in df.columns:
        if col.startswith("_"):
            continue
        is_null_mask = df[col].isna() | df[col].astype(str).str.strip().isin(["", "nan", "NaN", "None", "null", "NULL"])
        count = int(is_null_mask.sum())
        report.missing_counts[col] = count
        
        # Mandatory columns cannot be missing
        if col in ["customer_id", "product_id", "sale_date", "sales_amount", "quantity"]:
            for idx in df[is_null_mask].index:
                report.add_issue(idx, f"Mandatory column '{col}' is missing/empty", is_fatal=True)


# Check 2: Find exact duplicate records
def check_duplicates(df: pd.DataFrame, report: ValidationReport) -> None:
    data_cols = [c for c in df.columns if not c.startswith("_")]
    exact_dupes = df.duplicated(subset=data_cols, keep="first")
    report.duplicate_count = int(exact_dupes.sum())

    for idx in df[exact_dupes].index:
        report.add_issue(idx, "Exact duplicate record detected", is_fatal=False)


# Check 3: Check sales amount and quantity are positive numbers
def check_numeric_ranges(df: pd.DataFrame, report: ValidationReport) -> None:
    if "sales_amount" in df.columns:
        cleaned_amount = df["sales_amount"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.strip()
        numeric_amounts = pd.to_numeric(cleaned_amount, errors="coerce")
        neg_or_zero_sales = numeric_amounts <= 0
        for idx in df[neg_or_zero_sales.fillna(False)].index:
            report.negative_or_zero_sales += 1
            report.add_issue(idx, f"Non-positive sales_amount: {df.loc[idx, 'sales_amount']}", is_fatal=True)

    if "quantity" in df.columns:
        numeric_qty = pd.to_numeric(df["quantity"], errors="coerce")
        neg_or_zero_qty = numeric_qty <= 0
        for idx in df[neg_or_zero_qty.fillna(False)].index:
            report.negative_or_zero_qty += 1
            report.add_issue(idx, f"Non-positive quantity: {df.loc[idx, 'quantity']}", is_fatal=True)


# Check 4: Check date formats and reject future dates
def check_date_validity(df: pd.DataFrame, report: ValidationReport, max_future_date: Optional[date] = None) -> None:
    if "sale_date" not in df.columns:
        return

    if max_future_date is None:
        max_future_date = datetime.now().date()

    parsed_dates = pd.to_datetime(df["sale_date"], errors="coerce")

    # Find unparseable dates
    unparseable = parsed_dates.isna() & df["sale_date"].notna()
    for idx in df[unparseable].index:
        report.invalid_dates += 1
        report.add_issue(idx, f"Invalid unparseable date format: '{df.loc[idx, 'sale_date']}'", is_fatal=True)

    # Check future or invalid past dates
    for idx, parsed_dt in parsed_dates.dropna().items():
        dt_val = parsed_dt.date()
        if dt_val > max_future_date:
            report.future_dates += 1
            report.add_issue(idx, f"Future dated transaction: {dt_val} (max allowed: {max_future_date})", is_fatal=True)
        elif dt_val.year < 2000:
            report.invalid_dates += 1
            report.add_issue(idx, f"Anachronistic date before year 2000: {dt_val}", is_fatal=True)


# Check 5: Check customer and product foreign keys exist in master tables
def check_orphan_references(
    df: pd.DataFrame, 
    report: ValidationReport,
    valid_customer_ids: Optional[Set[int]] = None,
    valid_product_ids: Optional[Set[int]] = None
) -> None:
    if "customer_id" in df.columns:
        cust_numeric = pd.to_numeric(df["customer_id"], errors="coerce")
        invalid_cust = cust_numeric.isna() | (cust_numeric <= 0)
        for idx in df[invalid_cust].index:
            report.orphan_customers += 1
            report.add_issue(idx, f"Malformed/Negative customer_id: '{df.loc[idx, 'customer_id']}'", is_fatal=True)

        if valid_customer_ids is not None:
            for idx, cid in cust_numeric.dropna().items():
                if int(cid) not in valid_customer_ids:
                    report.orphan_customers += 1
                    report.add_issue(idx, f"Orphan customer_id {int(cid)} not found in master database", is_fatal=True)

    if "product_id" in df.columns:
        prod_numeric = pd.to_numeric(df["product_id"], errors="coerce")
        invalid_prod = prod_numeric.isna() | (prod_numeric <= 0)
        for idx in df[invalid_prod].index:
            report.orphan_products += 1
            report.add_issue(idx, f"Malformed/Negative product_id: '{df.loc[idx, 'product_id']}'", is_fatal=True)

        if valid_product_ids is not None:
            for idx, pid in prod_numeric.dropna().items():
                if int(pid) not in valid_product_ids:
                    report.orphan_products += 1
                    report.add_issue(idx, f"Orphan product_id {int(pid)} not found in master database", is_fatal=True)


# Check 6: Check column data types
def check_data_types(df: pd.DataFrame, report: ValidationReport) -> None:
    if "sales_amount" in df.columns:
        raw_vals = df["sales_amount"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.strip()
        non_numeric = pd.to_numeric(raw_vals, errors="coerce").isna() & df["sales_amount"].notna()
        count = int(non_numeric.sum())
        report.dtype_errors["sales_amount"] = count
        for idx in df[non_numeric].index:
            report.add_issue(idx, f"sales_amount contains non-numeric characters: '{df.loc[idx, 'sales_amount']}'", is_fatal=True)

    if "quantity" in df.columns:
        non_int = pd.to_numeric(df["quantity"], errors="coerce").isna() & df["quantity"].notna()
        count = int(non_int.sum())
        report.dtype_errors["quantity"] = count
        for idx in df[non_int].index:
            report.add_issue(idx, f"quantity is not a valid integer: '{df.loc[idx, 'quantity']}'", is_fatal=True)


# Run all 6 data quality checks
def run_checks(
    df: pd.DataFrame,
    valid_customer_ids: Optional[Set[int]] = None,
    valid_product_ids: Optional[Set[int]] = None,
    max_future_date: Optional[date] = None,
    engine: Optional[Any] = None
) -> ValidationReport:
    if df.empty:
        return ValidationReport(0)

    # Fetch reference IDs from database for sales fact tables
    if engine is not None:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                if valid_customer_ids is None and "customer_id" in df.columns and "customer_name" not in df.columns:
                    valid_customer_ids = set(int(x) for x in conn.execute(text("SELECT customer_id FROM customers")).scalars().all())
                if valid_product_ids is None and "product_id" in df.columns and "product_name" not in df.columns:
                    valid_product_ids = set(int(x) for x in conn.execute(text("SELECT product_id FROM products")).scalars().all())
        except Exception as exc:
            logger.debug("Notice querying master tables for validation: %s", exc)

    report = ValidationReport(total_rows=len(df))

    check_missing_values(df, report)
    check_duplicates(df, report)
    check_numeric_ranges(df, report)
    check_date_validity(df, report, max_future_date=max_future_date)
    check_orphan_references(df, report, valid_customer_ids, valid_product_ids)
    check_data_types(df, report)

    return report
