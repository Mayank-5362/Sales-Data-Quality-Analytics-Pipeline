"""
Sample Data Generator
Creates sample monthly sales datasets and intentionally dirty CSVs for testing and demonstration.
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from src.config import BASE_DIR

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Master Dimensions Data
CUSTOMERS = [
    (101, "Acme Corporation", "North"),
    (102, "Global Tech Industries", "South"),
    (103, "Apex Retailers Ltd", "East"),
    (104, "Vanguard Logistics", "West"),
    (105, "Horizon Health Inc", "Central"),
    (106, "Pinnacle Capital", "EMEA"),
    (107, "Summit Energy Solutions", "APAC"),
    (108, "Starlight Media Group", "North"),
    (109, "Nexus Software Labs", "West"),
    (110, "Quantum Dynamics", "East"),
]

PRODUCTS = [
    (201, "Cloud Enterprise Server", "Hardware"),
    (202, "Analytics SaaS License", "Software"),
    (203, "Ergonomic Workstation Pro", "Office Supplies"),
    (204, "Cybersecurity Suite 360", "Software"),
    (205, "Ultra HD Video Conference Bar", "Hardware"),
    (206, "Data Engineering Support Plan", "Services"),
    (207, "Managed Database Cluster", "Cloud"),
    (208, "Business Intelligence Dashboard", "Software"),
]


def generate_clean_monthly_csv(year: int, month: int, num_records: int = 50) -> Path:
    """
    Generates a realistic clean monthly sales CSV.
    """
    filename = f"sales_{year}_{month:02d}.csv"
    file_path = RAW_DATA_DIR / filename

    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    days_in_month = (end_date - start_date).days + 1

    records = []
    for _ in range(num_records):
        cust = random.choice(CUSTOMERS)
        prod = random.choice(PRODUCTS)
        random_day = random.randint(0, days_in_month - 1)
        sale_dt = (start_date + timedelta(days=random_day)).strftime("%Y-%m-%d")
        qty = random.randint(1, 20)
        
        # Base pricing per product
        base_price_map = {201: 1500.0, 202: 350.0, 203: 420.0, 204: 800.0, 205: 950.0, 206: 2500.0, 207: 3200.0, 208: 600.0}
        unit_price = base_price_map.get(prod[0], 500.0)
        # Apply slight random variation
        unit_price = round(unit_price * random.uniform(0.9, 1.1), 2)
        sales_amount = round(qty * unit_price, 2)

        records.append({
            "customer_id": cust[0],
            "customer_name": cust[1],
            "region": cust[2],
            "product_id": prod[0],
            "product_name": prod[1],
            "category": prod[2],
            "sale_date": sale_dt,
            "quantity": qty,
            "sales_amount": sales_amount
        })

    df = pd.DataFrame(records)
    df.to_csv(file_path, index=False)
    print(f"Generated clean dataset: {file_path.name} ({len(df)} rows)")
    return file_path


def generate_dirty_sample_csv() -> Path:
    """
    Generates an intentionally dirty sample CSV with all 6 categories of real-world DQ issues:
    1. Whitespace padding in strings
    2. Mixed/corrupted casing ('eLeCtrOnIcS', 'north')
    3. Currency formatting strings ('$1,500.50')
    4. Exact duplicate rows
    5. Missing/blank values in various columns
    6. Non-positive numbers (negative sales, zero quantity)
    7. Invalid and future dates ('2099-12-31', 'invalid-date-format')
    8. Negative/Orphan customer and product IDs
    """
    filename = "sample_dirty_sales.csv"
    file_path = RAW_DATA_DIR / filename

    dirty_rows = [
        # Normal clean baseline rows
        {"customer_id": "101", "customer_name": "Acme Corporation", "region": "North", "product_id": "201", "product_name": "Cloud Enterprise Server", "category": "Hardware", "sale_date": "2024-04-05", "quantity": "3", "sales_amount": "4500.00"},
        {"customer_id": "102", "customer_name": "Global Tech Industries", "region": "South", "product_id": "202", "product_name": "Analytics SaaS License", "category": "Software", "sale_date": "2024-04-06", "quantity": "5", "sales_amount": "1750.00"},
        
        # Issue 1: Whitespace padding in strings
        {"customer_id": " 103 ", "customer_name": "  Apex Retailers Ltd  ", "region": " East ", "product_id": "203", "product_name": " Ergonomic Workstation Pro ", "category": " Office Supplies ", "sale_date": "2024-04-07", "quantity": "2", "sales_amount": "840.00"},
        
        # Issue 2: Mixed & weird casing (should be auto-standardized by transform)
        {"customer_id": "104", "customer_name": "vanguard logistics", "region": "wEsT", "product_id": "204", "product_name": "CYBERSECURITY SUITE 360", "category": "sOfTwArE", "sale_date": "2024-04-08", "quantity": "4", "sales_amount": "3200.00"},
        {"customer_id": "106", "customer_name": "Pinnacle Capital", "region": "emea", "product_id": "207", "product_name": "Managed Database Cluster", "category": "cloud", "sale_date": "2024-04-09", "quantity": "1", "sales_amount": "3200.00"},

        # Issue 3: Formatted currency strings with dollar signs and commas
        {"customer_id": "105", "customer_name": "Horizon Health Inc", "region": "Central", "product_id": "205", "product_name": "Ultra HD Video Conference Bar", "category": "Hardware", "sale_date": "2024-04-10", "quantity": "2", "sales_amount": "$1,900.00"},
        
        # Issue 4: Exact duplicate rows (should be deduplicated to 1)
        {"customer_id": "107", "customer_name": "Summit Energy Solutions", "region": "APAC", "product_id": "206", "product_name": "Data Engineering Support Plan", "category": "Services", "sale_date": "2024-04-11", "quantity": "1", "sales_amount": "2500.00"},
        {"customer_id": "107", "customer_name": "Summit Energy Solutions", "region": "APAC", "product_id": "206", "product_name": "Data Engineering Support Plan", "category": "Services", "sale_date": "2024-04-11", "quantity": "1", "sales_amount": "2500.00"},

        # Issue 5: Non-critical missing values (should be imputed by transform)
        {"customer_id": "108", "customer_name": "", "region": "", "product_id": "208", "product_name": "", "category": "", "sale_date": "2024-04-12", "quantity": "6", "sales_amount": "3600.00"},
        
        # Issue 6 (FATAL): Negative sales amount (must be quarantined)
        {"customer_id": "109", "customer_name": "Nexus Software Labs", "region": "West", "product_id": "202", "product_name": "Analytics SaaS License", "category": "Software", "sale_date": "2024-04-13", "quantity": "3", "sales_amount": "-1050.00"},

        # Issue 7 (FATAL): Zero / Negative quantity (must be quarantined)
        {"customer_id": "110", "customer_name": "Quantum Dynamics", "region": "East", "product_id": "201", "product_name": "Cloud Enterprise Server", "category": "Hardware", "sale_date": "2024-04-14", "quantity": "0", "sales_amount": "1500.00"},
        {"customer_id": "101", "customer_name": "Acme Corporation", "region": "North", "product_id": "203", "product_name": "Ergonomic Workstation Pro", "category": "Office Supplies", "sale_date": "2024-04-15", "quantity": "-2", "sales_amount": "840.00"},

        # Issue 8 (FATAL): Corrupt & unparseable date (must be quarantined)
        {"customer_id": "102", "customer_name": "Global Tech Industries", "region": "South", "product_id": "204", "product_name": "Cybersecurity Suite 360", "category": "Software", "sale_date": "CORRUPTED_DATE_VAL", "quantity": "2", "sales_amount": "1600.00"},

        # Issue 9 (FATAL): Future date beyond bounds (must be quarantined)
        {"customer_id": "103", "customer_name": "Apex Retailers Ltd", "region": "East", "product_id": "205", "product_name": "Ultra HD Video Conference Bar", "category": "Hardware", "sale_date": "2099-12-31", "quantity": "1", "sales_amount": "950.00"},

        # Issue 10 (FATAL): Missing mandatory foreign key customer_id (must be quarantined)
        {"customer_id": "", "customer_name": "Ghost Account", "region": "Central", "product_id": "206", "product_name": "Data Engineering Support Plan", "category": "Services", "sale_date": "2024-04-18", "quantity": "1", "sales_amount": "2500.00"},

        # Issue 11 (FATAL): Negative / non-numeric product_id (must be quarantined)
        {"customer_id": "104", "customer_name": "Vanguard Logistics", "region": "West", "product_id": "-999", "product_name": "Invalid Product Item", "category": "Hardware", "sale_date": "2024-04-19", "quantity": "2", "sales_amount": "1900.00"},

        # Additional clean records for summary volume
        {"customer_id": "105", "customer_name": "Horizon Health Inc", "region": "Central", "product_id": "201", "product_name": "Cloud Enterprise Server", "category": "Hardware", "sale_date": "2024-04-20", "quantity": "4", "sales_amount": "6000.00"},
        {"customer_id": "106", "customer_name": "Pinnacle Capital", "region": "EMEA", "product_id": "208", "product_name": "Business Intelligence Dashboard", "category": "Software", "sale_date": "2024-04-21", "quantity": "5", "sales_amount": "3000.00"},
    ]

    df = pd.DataFrame(dirty_rows)
    df.to_csv(file_path, index=False)
    print(f"Generated intentionally dirty dataset: {file_path.name} ({len(df)} rows)")
    return file_path


def generate_all():
    print("Generating sample test datasets in data/raw/ ...")
    generate_dirty_sample_csv()
    generate_clean_monthly_csv(2024, 1, 40)
    generate_clean_monthly_csv(2024, 2, 45)
    generate_clean_monthly_csv(2024, 3, 50)
    print("All sample datasets successfully created.")


if __name__ == "__main__":
    generate_all()
