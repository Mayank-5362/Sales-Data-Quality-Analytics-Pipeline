# REST API and web server for dashboard
import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import pandas as pd
from sqlalchemy import text

from src.config import get_engine, BASE_DIR
from src import extract, validate, transform, load, report
from scripts.init_db import init_database
from scripts.generate_sample_data import generate_all

WEB_DIR = BASE_DIR / "web"
REPORTS_DIR = BASE_DIR / "reports"
QUARANTINE_DIR = BASE_DIR / "data" / "quarantine"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"


# Custom HTTP request handler for API routes and static files
class PipelineRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Serve generated chart image
        if path == "/reports/sales_analytics_charts.png":
            chart_file = REPORTS_DIR / "sales_analytics_charts.png"
            if chart_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache")
                with open(chart_file, "rb") as f:
                    content = f.read()
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                return
            else:
                self.send_error(404, "Chart not yet generated.")
                return

        # Check database connection status
        if path == "/api/status":
            try:
                engine = get_engine()
                dialect = engine.dialect.name
                self._send_json({"status": "ONLINE", "database": dialect.upper()})
            except Exception as exc:
                self._send_json({"status": "OFFLINE", "error": str(exc)}, status=500)
            return

        # Return dashboard KPI metrics
        if path == "/api/kpis":
            try:
                engine = get_engine()
                kpis = report.fetch_executive_kpis(engine)
                self._send_json(kpis)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        # Return monthly and regional sales trends
        if path == "/api/trends":
            try:
                engine = get_engine()
                monthly_df = report.fetch_monthly_trends(engine)
                regional_df = report.fetch_regional_breakdown(engine)
                self._send_json({
                    "monthly": monthly_df.to_dict(orient="records"),
                    "regional": regional_df.to_dict(orient="records")
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        # Return data quality audit log entries
        if path == "/api/audit-logs":
            try:
                engine = get_engine()
                logs_df = report.fetch_data_quality_audit(engine)
                self._send_json(logs_df.to_dict(orient="records"))
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        # Return quarantined rejected records
        if path == "/api/quarantine":
            try:
                quar_files = sorted(list(QUARANTINE_DIR.glob("*.csv")), reverse=True)
                results = []
                for f in quar_files[:5]:
                    df = pd.read_csv(f)
                    results.append({
                        "file_name": f.name,
                        "row_count": len(df),
                        "rows": df.head(50).to_dict(orient="records")
                    })
                self._send_json(results)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        # Return list of raw CSV files in data folder
        if path == "/api/raw-files":
            try:
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                raw_files = [f.name for f in sorted(list(RAW_DIR.glob("*.csv")))]
                self._send_json(raw_files)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body_data = {}
        if content_len > 0:
            try:
                body_data = json.loads(self.rfile.read(content_len).decode("utf-8"))
            except Exception:
                pass

        # Reset and initialize database schema
        if path == "/api/init-db":
            try:
                init_database()
                self._send_json({"success": True, "message": "Database schema successfully initialized."})
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        # Generate sample demo datasets
        if path == "/api/generate-data":
            try:
                generate_all()
                self._send_json({"success": True, "message": "Sample monthly and dirty CSV datasets generated."})
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        # Trigger ETL pipeline execution
        if path == "/api/run-pipeline":
            try:
                engine = get_engine()
                file_target = body_data.get("file")
                results = []

                if file_target:
                    target_path = RAW_DIR / file_target
                    if not target_path.exists():
                        self._send_json({"success": False, "error": f"File {file_target} not found"}, status=404)
                        return
                    from main import run_pipeline_for_file
                    res = run_pipeline_for_file(target_path, engine=engine)
                    results.append(res)
                else:
                    from main import run_full_pipeline
                    run_full_pipeline(engine=engine)
                    results.append({"status": "ALL_PROCESSED"})

                report_out = report.generate(engine=engine)
                kpis = report.fetch_executive_kpis(engine)

                self._send_json({
                    "success": True,
                    "message": "Pipeline processed successfully.",
                    "results": results,
                    "kpis": kpis
                })
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        # Upload a CSV file
        if path == "/api/upload-csv":
            try:
                filename = body_data.get("filename", "uploaded_sales.csv")
                content = body_data.get("content", "")
                if not content:
                    self._send_json({"success": False, "error": "No CSV content provided."}, status=400)
                    return
                clean_name = Path(filename).name
                if not clean_name.endswith(".csv"):
                    clean_name += ".csv"
                dest = RAW_DIR / clean_name
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
                self._send_json({"success": True, "filename": clean_name, "message": f"Successfully uploaded {clean_name}"})
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        # Execute custom SQL query
        if path == "/api/query":
            try:
                engine = get_engine()
                query_sql = body_data.get("sql", "").strip()
                if not query_sql:
                    self._send_json({"success": False, "error": "No SQL query provided."}, status=400)
                    return

                cleaned_lines = []
                for line in query_sql.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("--") or stripped.startswith("//"):
                        continue
                    cleaned_lines.append(line)
                cleaned_sql = "\n".join(cleaned_lines).strip()

                if not cleaned_sql:
                    self._send_json({"success": False, "error": "Query is empty after removing comments."}, status=400)
                    return

                first_word = cleaned_sql.split()[0].upper()
                if first_word not in ["SELECT", "WITH"]:
                    self._send_json({"success": False, "error": "Only SELECT and WITH queries are permitted in query studio."}, status=400)
                    return

                dialect = engine.dialect.name
                if dialect == "sqlite":
                    query_sql = query_sql.replace("DATE_FORMAT(s.sale_date, '%Y-%m')", "strftime('%Y-%m', s.sale_date)")
                    query_sql = query_sql.replace("DATE_FORMAT(sale_date, '%Y-%m')", "strftime('%Y-%m', sale_date)")

                res_df = pd.read_sql(text(query_sql), engine)
                self._send_json({
                    "success": True,
                    "row_count": len(res_df),
                    "columns": list(res_df.columns),
                    "rows": res_df.to_dict(orient="records")
                })
            except Exception as exc:
                self._send_json({"success": False, "error": str(exc)}, status=500)
            return

        self.send_error(404, "API Endpoint Not Found")


# Start local web server
def run_server(port=5000):
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    server_address = ("", port)
    httpd = HTTPServer(server_address, PipelineRequestHandler)
    print(f">> Web UI server running at: http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    port = 5000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
