# Main CLI and pipeline orchestrator
import argparse
import sys
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import text

from src.config import get_engine, BASE_DIR
from src import extract, validate, transform, load, report
from scripts.init_db import init_database
from scripts.generate_sample_data import generate_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PipelineOrchestrator")


# Run ETL steps for a dataframe
def run_pipeline_for_dataframe(df: pd.DataFrame, source_name: str, engine=None, file_hash: str = None) -> dict:
    if df.empty:
        return {"status": "SKIPPED", "reason": "Empty dataset"}

    if engine is None:
        engine = get_engine()

    # 1. Validate data quality
    initial_report = validate.run_checks(df, engine=engine)

    # 2. Clean and transform
    clean_df, quarantine_df, transform_stats = transform.clean(df, initial_report, engine=engine)

    # 3. Load clean records to database
    load_result = load.load_to_database(
        clean_df=clean_df,
        quarantine_df=quarantine_df,
        stats=transform_stats,
        file_name=source_name,
        engine=engine,
        file_hash=file_hash
    )

    return {
        "status": "SUCCESS",
        "source": source_name,
        "initial_rows": transform_stats["initial_rows"],
        "clean_rows": transform_stats["cleaned_rows"],
        "quarantined_rows": transform_stats["quarantined_rows"],
        "duplicates_removed": transform_stats["duplicates_removed"],
        "missing_fixed": transform_stats["missing_fixed"],
        "load_result": load_result
    }


# Run ETL for a single CSV file
def run_pipeline_for_file(file_path: Path, engine=None, force: bool = False) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {"status": "ERROR", "message": f"File not found: {path}"}

    if engine is None:
        engine = get_engine()

    # Check if file was already ingested
    file_hash = extract.compute_sha256(path)
    if not force and load.is_file_already_processed(file_hash, engine):
        return {
            "status": "ALREADY_PROCESSED",
            "source": path.name,
            "message": "File was already ingested previously. Skipped to prevent duplicate inflation."
        }

    df, metadata = extract.read_csv_file(path)
    return run_pipeline_for_dataframe(df, source_name=path.name, engine=engine, file_hash=file_hash)


# Run ETL on all raw CSV files in data folder
def run_full_pipeline(data_dir: str = "data/raw", engine=None, force: bool = False) -> None:
    if engine is None:
        engine = get_engine()

    raw_path = Path(data_dir)
    csv_files = list(raw_path.glob("*.csv"))
    if not csv_files:
        return

    # Ingest dimension tables before fact tables
    def file_sort_key(p: Path):
        name = p.name.lower()
        if "customer" in name:
            return (0, name)
        if "product" in name:
            return (1, name)
        return (2, name)

    csv_files = sorted(csv_files, key=file_sort_key)
    results = []

    for file_path in csv_files:
        res = run_pipeline_for_file(file_path, engine=engine, force=force)
        results.append(res)

    # Generate analytics report
    report.generate(engine=engine)


# Run analytical SQL queries from file
def run_sql_analytics(engine=None):
    if engine is None:
        engine = get_engine()

    queries_file = BASE_DIR / "sql" / "analysis_queries.sql"
    if not queries_file.exists():
        return

    with open(queries_file, "r", encoding="utf-8") as f:
        content = f.read()

    raw_queries = [q.strip() for q in content.split(";") if q.strip() and "SELECT" in q.upper()]

    print("\n" + "=" * 80)
    print("                RUNNING ADVANCED SQL ANALYTICAL QUERIES")
    print("=" * 80)

    for i, q in enumerate(raw_queries, start=1):
        title = f"Query {i}"
        for line in q.split("\n"):
            if line.strip().startswith("--") and ("." in line or "Name:" in line or "Top" in line or "Month" in line or "Sales" in line or "Customer" in line):
                title = line.replace("--", "").strip()
                break

        print(f"\n>> [{i}/{len(raw_queries)}] {title}")
        print("-" * 80)

        try:
            res_df = pd.read_sql(text(q), engine)
            if res_df.empty:
                print("   (No matching records found)")
            else:
                from tabulate import tabulate
                print(tabulate(res_df, headers="keys", tablefmt="grid", showindex=False))
        except Exception as exc:
            logger.warning("Could not execute query [%s]: %s", title, exc)

    print("\n" + "=" * 80 + "\n")


# Parse CLI command line flags
def parse_args():
    parser = argparse.ArgumentParser(description="Automated Sales Data Quality & Analytics Pipeline")
    parser.add_argument("--init-db", action="store_true", help="Initialize database schema and tables")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample monthly and dirty CSV datasets")
    parser.add_argument("--run", action="store_true", help="Execute the complete end-to-end pipeline on data/raw/")
    parser.add_argument("--file", type=str, help="Process a single CSV file path")
    parser.add_argument("--report-only", action="store_true", help="Generate executive dashboard reports and charts")
    parser.add_argument("--analytics-queries", action="store_true", help="Execute advanced analytical SQL queries")
    parser.add_argument("--ui", action="store_true", help="Launch the interactive Web UI and REST API server")
    return parser.parse_args()


# Main execution entrypoint
def main():
    args = parse_args()

    if not any([args.init_db, args.generate_sample, args.run, args.file, args.report_only, args.analytics_queries, args.ui]):
        init_database()
        generate_all()
        run_full_pipeline()
        run_sql_analytics()
        return

    if args.init_db:
        init_database()

    if args.generate_sample:
        generate_all()

    if args.file:
        engine = get_engine()
        res = run_pipeline_for_file(Path(args.file), engine=engine)
        print(res)
        report.generate(engine=engine)

    if args.run:
        run_full_pipeline()

    if args.report_only:
        report.generate()

    if args.analytics_queries:
        run_sql_analytics()

    if args.ui:
        from server import run_server
        run_server(port=5000)


if __name__ == "__main__":
    main()
