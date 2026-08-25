# Analytics reporting and chart generation module
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from tabulate import tabulate
import matplotlib.pyplot as plt

from src.config import get_engine

logger = logging.getLogger("ReportGenerator")


# Fetch top level KPI metrics from database
def fetch_executive_kpis(engine: Engine) -> Dict[str, Any]:
    with engine.connect() as conn:
        sales_summary = conn.execute(text("""
            SELECT 
                COUNT(sale_id) AS total_orders,
                COALESCE(SUM(quantity), 0) AS total_units_sold,
                COALESCE(SUM(sales_amount), 0.0) AS total_revenue,
                COALESCE(AVG(sales_amount), 0.0) AS avg_order_value,
                MIN(sale_date) AS earliest_sale,
                MAX(sale_date) AS latest_sale
            FROM sales;
        """)).mappings().first()

        top_region = conn.execute(text("""
            SELECT c.region, SUM(s.sales_amount) AS revenue
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY revenue DESC
            LIMIT 1;
        """)).mappings().first()

        top_product = conn.execute(text("""
            SELECT p.product_name, p.category, SUM(s.sales_amount) AS revenue
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            GROUP BY p.product_name, p.category
            ORDER BY revenue DESC
            LIMIT 1;
        """)).mappings().first()

        top_customer = conn.execute(text("""
            SELECT c.customer_name, c.region, SUM(s.sales_amount) AS revenue
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            GROUP BY c.customer_name, c.region
            ORDER BY revenue DESC
            LIMIT 1;
        """)).mappings().first()

    return {
        "total_orders": sales_summary["total_orders"] if sales_summary else 0,
        "total_units_sold": sales_summary["total_units_sold"] if sales_summary else 0,
        "total_revenue": float(sales_summary["total_revenue"]) if sales_summary else 0.0,
        "avg_order_value": float(sales_summary["avg_order_value"]) if sales_summary else 0.0,
        "date_range": f"{sales_summary['earliest_sale']} to {sales_summary['latest_sale']}" if sales_summary and sales_summary["earliest_sale"] else "N/A",
        "top_region": top_region["region"] if top_region else "N/A",
        "top_region_revenue": float(top_region["revenue"]) if top_region else 0.0,
        "top_product": top_product["product_name"] if top_product else "N/A",
        "top_product_revenue": float(top_product["revenue"]) if top_product else 0.0,
        "top_customer": top_customer["customer_name"] if top_customer else "N/A",
        "top_customer_revenue": float(top_customer["revenue"]) if top_customer else 0.0,
    }


# Fetch monthly revenue summary
def fetch_monthly_trends(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT 
            strftime('%Y-%m', sale_date) AS month,
            COUNT(sale_id) AS orders,
            SUM(quantity) AS units,
            SUM(sales_amount) AS revenue
        FROM sales
        GROUP BY strftime('%Y-%m', sale_date)
        ORDER BY month ASC;
    """
    return pd.read_sql(query, engine)


# Fetch regional sales breakdown
def fetch_regional_breakdown(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT 
            c.region,
            COUNT(s.sale_id) AS total_orders,
            SUM(s.sales_amount) AS total_revenue
        FROM sales s
        JOIN customers c ON s.customer_id = c.customer_id
        GROUP BY c.region
        ORDER BY total_revenue DESC;
    """
    return pd.read_sql(query, engine)


# Fetch recent data quality audit logs
def fetch_data_quality_audit(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT 
            log_id,
            run_date,
            file_name,
            records_read,
            duplicates_removed,
            missing_fixed,
            invalid_rows,
            records_loaded,
            status
        FROM data_quality_log
        ORDER BY log_id DESC
        LIMIT 10;
    """
    return pd.read_sql(query, engine)


# Print executive summary to console
def print_console_report(
    kpis: Dict[str, Any],
    monthly_df: pd.DataFrame,
    regional_df: pd.DataFrame,
    dq_df: pd.DataFrame
) -> str:
    divider = "=" * 80
    sub_divider = "-" * 80

    output_lines = [
        "",
        divider,
        "   AUTOMATED SALES DATA QUALITY & ANALYTICS PIPELINE REPORT",
        divider,
        f"Generated At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Active Period: {kpis.get('date_range', 'N/A')}",
        sub_divider,
        " 1. EXECUTIVE KPI SUMMARY",
        sub_divider,
        f" * Total Revenue           : ${kpis.get('total_revenue', 0.0):,.2f}",
        f" * Total Transactions      : {kpis.get('total_orders', 0):,} orders",
        f" * Total Units Sold        : {kpis.get('total_units_sold', 0):,} units",
        f" * Average Order Value     : ${kpis.get('avg_order_value', 0.0):,.2f}",
        f" * Top Performing Region   : {kpis.get('top_region', 'N/A')} (${kpis.get('top_region_revenue', 0.0):,.2f})",
        f" * Top Selling Product     : {kpis.get('top_product', 'N/A')} (${kpis.get('top_product_revenue', 0.0):,.2f})",
        f" * Most Valuable Customer  : {kpis.get('top_customer', 'N/A')} (${kpis.get('top_customer_revenue', 0.0):,.2f})",
        "",
        sub_divider,
        " 2. MONTHLY REVENUE & VOLUME TREND",
        sub_divider,
    ]

    if not monthly_df.empty:
        monthly_display = monthly_df.copy()
        monthly_display["revenue"] = monthly_display["revenue"].apply(lambda x: f"${x:,.2f}")
        output_lines.append(tabulate(monthly_display, headers="keys", tablefmt="grid", showindex=False))
    else:
        output_lines.append("No monthly transaction data available.")

    output_lines.extend([
        "",
        sub_divider,
        " 3. REGIONAL PERFORMANCE BREAKDOWN",
        sub_divider,
    ])

    if not regional_df.empty:
        regional_display = regional_df.copy()
        total_rev = regional_df["total_revenue"].sum()
        regional_display["share_%"] = regional_display["total_revenue"].apply(lambda x: f"{(x / total_rev * 100):.1f}%" if total_rev > 0 else "0.0%")
        regional_display["total_revenue"] = regional_display["total_revenue"].apply(lambda x: f"${x:,.2f}")
        output_lines.append(tabulate(regional_display, headers="keys", tablefmt="grid", showindex=False))
    else:
        output_lines.append("No regional transaction data available.")

    output_lines.extend([
        "",
        sub_divider,
        " 4. DATA QUALITY & INGESTION AUDIT LOG",
        sub_divider,
    ])

    if not dq_df.empty:
        output_lines.append(tabulate(dq_df, headers="keys", tablefmt="grid", showindex=False))
    else:
        output_lines.append("No data quality execution logs recorded.")

    output_lines.append(divider)
    report_text = "\n".join(output_lines)
    print(report_text)
    return report_text


# Save text summary report to reports directory
def save_text_report(report_text: str, reports_dir: str = "reports") -> str:
    dir_path = Path(reports_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"sales_report_{datetime.now().strftime('%Y-%m')}.txt"
    file_path = dir_path / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return str(file_path)


# Generate monthly trend and regional charts
def generate_charts(
    monthly_df: pd.DataFrame,
    regional_df: pd.DataFrame,
    reports_dir: str = "reports"
) -> Optional[str]:
    if monthly_df.empty and regional_df.empty:
        return None

    dir_path = Path(reports_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    chart_path = dir_path / "sales_analytics_charts.png"

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Sales Performance & Revenue Analytics Dashboard", fontsize=16, fontweight="bold")

    # 1. Monthly revenue trend chart
    if not monthly_df.empty:
        axes[0].plot(monthly_df["month"], monthly_df["revenue"], marker="o", color="#2563EB", linewidth=2.5, markersize=8)
        axes[0].set_title("Monthly Revenue Trend ($)", fontsize=13, fontweight="bold")
        axes[0].set_xlabel("Month", fontsize=11)
        axes[0].set_ylabel("Revenue ($)", fontsize=11)
        axes[0].grid(True, linestyle="--", alpha=0.5)
        axes[0].tick_params(axis="x", rotation=45)
        for idx, row in monthly_df.iterrows():
            m_val = str(row["month"])
            r_val = float(row["revenue"])
            axes[0].annotate(f"${r_val:,.0f}", (m_val, r_val), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)

    # 2. Regional revenue bar chart
    if not regional_df.empty:
        axes[1].bar(regional_df["region"], regional_df["total_revenue"], color="#10B981", edgecolor="#047857", width=0.5)
        axes[1].set_title("Revenue by Geographic Region ($)", fontsize=13, fontweight="bold")
        axes[1].set_xlabel("Region", fontsize=11)
        axes[1].set_ylabel("Revenue ($)", fontsize=11)
        axes[1].grid(axis="y", linestyle="--", alpha=0.5)
        for idx, row in regional_df.iterrows():
            reg_val = str(row["region"])
            tot_val = float(row["total_revenue"])
            axes[1].annotate(f"${tot_val:,.0f}", (reg_val, tot_val), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(chart_path, dpi=300)
    plt.close()
    return str(chart_path)


# Generate executive report and charts
def generate(engine: Optional[Engine] = None, reports_dir: str = "reports") -> Dict[str, Any]:
    if engine is None:
        engine = get_engine()

    kpis = fetch_executive_kpis(engine)
    monthly_df = fetch_monthly_trends(engine)
    regional_df = fetch_regional_breakdown(engine)
    dq_df = fetch_data_quality_audit(engine)

    report_text = print_console_report(kpis, monthly_df, regional_df, dq_df)
    report_file = save_text_report(report_text, reports_dir)
    chart_file = generate_charts(monthly_df, regional_df, reports_dir)

    return {
        "kpis": kpis,
        "report_file": report_file,
        "chart_file": chart_file
    }
