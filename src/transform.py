# Data transformation and cleaning module
import logging
from typing import Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
from src.validate import ValidationReport, run_checks

logger = logging.getLogger("DataTransformer")


# Trim whitespace and standardize text casing
def standardize_text(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    fixed_count = 0
    df = df.copy()

    # Trim whitespace on text columns
    for col in df.select_dtypes(include=["object", "string"]).columns:
        if col.startswith("_"):
            continue
        original = df[col].astype(str)
        trimmed = original.str.strip()
        diff = (original != trimmed) & original.notna()
        fixed_count += int(diff.sum())
        df[col] = trimmed

    # Standardize regions
    if "region" in df.columns:
        df["region"] = df["region"].astype(str).str.title()
        df["region"] = df["region"].replace({
            "Apac": "APAC", "Emea": "EMEA", "Latam": "LATAM",
            "Us": "US", "Usa": "USA", "Uk": "UK",
            "Nan": "Unknown", "None": "Unknown", "": "Unknown"
        })

    # Standardize categories
    if "category" in df.columns:
        df["category"] = df["category"].astype(str).str.title()
        df["category"] = df["category"].replace({"Nan": "General", "None": "General", "": "General"})

    if "customer_name" in df.columns:
        df["customer_name"] = df["customer_name"].astype(str).str.title()

    if "product_name" in df.columns:
        df["product_name"] = df["product_name"].astype(str).str.title()

    return df, fixed_count


# Clean currency signs and parse numbers and dates
def clean_and_coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Clean sales amounts
    if "sales_amount" in df.columns:
        cleaned = (
            df["sales_amount"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["sales_amount"] = pd.to_numeric(cleaned, errors="coerce").round(2)

    # Clean quantities
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # Clean customer and product IDs
    if "customer_id" in df.columns:
        df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")
    if "product_id" in df.columns:
        df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce")

    # Clean dates
    if "sale_date" in df.columns:
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.date

    return df


# Fill missing regions, categories, or names with defaults
def handle_missing_and_imputations(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    df = df.copy()
    imputed_count = 0

    if "region" in df.columns:
        missing_region = df["region"].isna() | (df["region"].astype(str).str.strip() == "") | (df["region"] == "Unknown") | (df["region"] == "nan")
        imputed_count += int(missing_region.sum())
        df.loc[missing_region, "region"] = "Unknown"

    if "category" in df.columns:
        missing_cat = df["category"].isna() | (df["category"].astype(str).str.strip() == "") | (df["category"] == "General") | (df["category"] == "nan")
        imputed_count += int(missing_cat.sum())
        df.loc[missing_cat, "category"] = "General"

    if "customer_name" in df.columns and "customer_id" in df.columns:
        missing_cname = df["customer_name"].isna() | (df["customer_name"].astype(str).str.strip() == "") | (df["customer_name"] == "Nan")
        for idx in df[missing_cname].index:
            cid = df.loc[idx, "customer_id"]
            df.loc[idx, "customer_name"] = f"Customer {int(cid)}" if pd.notna(cid) and str(cid).replace('.0','').isdigit() else "Valued Customer"
            imputed_count += 1

    if "product_name" in df.columns and "product_id" in df.columns:
        missing_pname = df["product_name"].isna() | (df["product_name"].astype(str).str.strip() == "") | (df["product_name"] == "Nan")
        for idx in df[missing_pname].index:
            pid = df.loc[idx, "product_id"]
            df.loc[idx, "product_name"] = f"Product {int(pid)}" if pd.notna(pid) and str(pid).replace('.0','').isdigit() else "Standard Product"
            imputed_count += 1

    return df, imputed_count


# Calculate unit price and year-month string
def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "sales_amount" in df.columns and "quantity" in df.columns:
        df["unit_price"] = np.where(
            df["quantity"] > 0,
            (df["sales_amount"] / df["quantity"]).round(2),
            0.00
        )

    if "sale_date" in df.columns:
        df["year_month"] = pd.to_datetime(df["sale_date"]).dt.strftime("%Y-%m")

    return df


# Main transformation workflow separating clean and quarantined records
def clean(
    df: pd.DataFrame,
    report: ValidationReport = None,
    engine: Optional[Any] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "initial_rows": 0, "cleaned_rows": 0, "quarantined_rows": 0,
            "duplicates_removed": 0, "missing_fixed": 0,
        }

    initial_count = len(df)

    # 1. Standardize string formatting
    df_clean, whitespace_fixed = standardize_text(df)

    # 2. Remove duplicate rows
    data_cols = [c for c in df_clean.columns if not c.startswith("_")]
    dupe_mask = df_clean.duplicated(subset=data_cols, keep="first")
    duplicates_removed = int(dupe_mask.sum())
    df_deduped = df_clean[~dupe_mask].copy().reset_index(drop=True)

    # 3. Cast data types
    df_typed = clean_and_coerce_types(df_deduped)

    # 4. Fill missing non-critical attributes
    df_imputed, missing_fixed = handle_missing_and_imputations(df_typed)

    # 5. Validate and separate clean vs invalid records
    val_report = run_checks(df_imputed, engine=engine)
    fatal_indices = val_report.fatal_row_indices
    valid_mask = ~df_imputed.index.isin(fatal_indices)

    clean_df = df_imputed[valid_mask].copy().reset_index(drop=True)
    quarantine_df = df_imputed[~valid_mask].copy().reset_index(drop=True)

    # Attach error reasons to quarantined records
    quarantine_reasons = []
    for orig_idx in fatal_indices:
        reasons = "; ".join(val_report.row_level_issues.get(orig_idx, ["Unknown Validation Failure"]))
        quarantine_reasons.append(reasons)
    if not quarantine_df.empty:
        quarantine_df["_rejection_reasons"] = quarantine_reasons

    # Cast clean IDs and numbers
    if not clean_df.empty:
        if "customer_id" in clean_df.columns:
            clean_df["customer_id"] = clean_df["customer_id"].astype(int)
        if "product_id" in clean_df.columns:
            clean_df["product_id"] = clean_df["product_id"].astype(int)
        if "quantity" in clean_df.columns:
            clean_df["quantity"] = clean_df["quantity"].astype(int)
        if "sales_amount" in clean_df.columns:
            clean_df["sales_amount"] = clean_df["sales_amount"].astype(float)
        clean_df = derive_features(clean_df)

    stats = {
        "initial_rows": initial_count,
        "duplicates_removed": duplicates_removed,
        "missing_fixed": missing_fixed + whitespace_fixed,
        "quarantined_rows": len(quarantine_df),
        "cleaned_rows": len(clean_df),
    }

    return clean_df, quarantine_df, stats
