# Sales Data Quality & Analytics Pipeline

An automated ETL pipeline and interactive web application for validating messy sales data, enforcing data quality rules, and running SQL analytics.

---

##  How It Works

The pipeline automates the complete data lifecycle across 5 stages:

```
[Raw CSVs] ➔ [Extract] ➔ [Validate] ➔ [Transform] ➔ [Load (SQLite)] ➔ [Analytics & Reports]
                              │
                              ▼
                      [Quarantine Folder] (Invalid / Orphan Records)
```

1. **Extract**: Reads CSVs with encoding fallback (`utf-8`, `latin1`) and computes SHA256 file checksums for idempotency.
2. **Validate**: Runs 6 Data Quality rules (nulls, duplicates, positive numeric bounds, valid dates, foreign key orphans, data types).
3. **Transform**: Standardizes text casing, coerces currency/numeric types, derives `unit_price`, and segregates clean rows from rejected rows.
4. **Load**: Upserts `customers` and `products` dimensions, inserts `sales` facts, logs audit metrics to `data_quality_log`, and archives quarantine CSVs.
5. **Report**: Generates executive KPI summaries, monthly & regional trend tables, and Matplotlib visualization charts.

---

##  Project Structure

```
├── data/
│   ├── raw/                 # Input CSV files (customers.csv, products.csv, sales.csv)
│   ├── processed/           # Cleaned and archived datasets
│   └── quarantine/          # Rejected records with failure reasons
├── sql/
│   ├── schema.sql           # Database tables, foreign keys, and indexes
│   └── analysis_queries.sql # Analytical queries (RANK, LAG, SUM OVER)
├── src/
│   ├── config.py            # SQLite connection with foreign key enforcement
│   ├── extract.py           # CSV extraction and SHA256 hashing
│   ├── validate.py          # 6-point Data Quality rule engine
│   ├── transform.py         # Data cleaning, type coercion, and quarantine routing
│   ├── load.py              # Dimensions upsert, facts loader, and idempotency tracking
│   └── report.py            # KPI calculation and chart generation
├── web/
│   ├── index.html           # Interactive dashboard and SQL Query Studio
│   ├── css/style.css        # Minimalist light-theme CSS
│   └── js/app.js            # Client-side API interactions and query execution
├── main.py                  # CLI pipeline orchestrator
├── server.py                # Local REST API server
└── ARCHITECTURE_AND_INTERVIEW_GUIDE.md # Deep-dive documentation & interview notes
```

---

##  Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Interactive Web Dashboard
```bash
python server.py 5000
```
Open **http://localhost:5000** in your browser to upload CSVs, run the pipeline, and execute custom SQL queries.

---

##  CLI Commands

```bash
# Ingest all CSV files in data/raw/ and generate executive report
python main.py --run

# Process a single CSV file
python main.py --file data/raw/sales.csv

# Execute analytical SQL queries in terminal
python main.py --analytics-queries

# Run complete test suite
pytest -v
```
