/**
 * Sales Analytics & Data Quality Pipeline
 * Interactive Web Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    checkDatabaseStatus();
    loadDashboardData();
    loadRawFiles();
    loadAuditLogs();
    loadQuarantineData();
    initSqlStudio();
    bindActionButtons();
});

/* ==========================================================================
   1. Tab Navigation
   ========================================================================== */
function initTabs() {
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add("active");
            }

            // Trigger specific refreshes on tab activation
            if (targetId === "tab-dashboard") loadDashboardData();
            if (targetId === "tab-audit") {
                loadAuditLogs();
                loadQuarantineData();
            }
        });
    });
}

/* ==========================================================================
   2. API Calls & Data Loaders
   ========================================================================== */
async function checkDatabaseStatus() {
    const badge = document.getElementById("dbStatusBadge");
    const textEl = document.getElementById("dbStatusText");

    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        if (data.status === "ONLINE") {
            badge.className = "status-badge status-online";
            textEl.textContent = `${data.database} ONLINE`;
        } else {
            badge.className = "status-badge status-loading";
            textEl.textContent = "DB OFFLINE";
        }
    } catch (err) {
        badge.className = "status-badge status-loading";
        textEl.textContent = "SERVER OFFLINE";
    }
}

async function loadDashboardData() {
    // 1. KPIs
    try {
        const res = await fetch("/api/kpis");
        const kpis = await res.json();
        if (kpis && !kpis.error) {
            document.getElementById("kpiRevenue").textContent = `$${Number(kpis.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            document.getElementById("kpiAvgOrder").textContent = `Avg Order: $${Number(kpis.avg_order_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            document.getElementById("kpiOrders").textContent = Number(kpis.total_orders || 0).toLocaleString();
            document.getElementById("kpiUnits").textContent = `${Number(kpis.total_units_sold || 0).toLocaleString()} units sold`;
            document.getElementById("kpiTopRegion").textContent = kpis.top_region || "N/A";
            document.getElementById("kpiTopRegionRev").textContent = `$${Number(kpis.top_region_revenue || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} revenue`;
            document.getElementById("kpiTopProduct").textContent = kpis.top_product || "N/A";
            document.getElementById("kpiTopCust").textContent = `Top Client: ${kpis.top_customer || 'N/A'}`;
        }
    } catch (err) {
        console.error("Failed loading KPIs:", err);
    }

    // 2. Regional Table
    try {
        const res = await fetch("/api/trends");
        const trends = await res.json();
        if (trends && trends.regional) {
            renderRegionalTable(trends.regional);
        }
    } catch (err) {
        console.error("Failed loading trends:", err);
    }

    // 3. Refresh Chart Image or show clean empty state
    const chartImg = document.getElementById("analyticsChartImg");
    const emptyState = document.getElementById("chartEmptyState");

    if (chartImg && emptyState) {
        const testImg = new Image();
        const chartUrl = `/reports/sales_analytics_charts.png?t=${new Date().getTime()}`;
        testImg.onload = () => {
            chartImg.src = chartUrl;
            chartImg.style.display = "block";
            emptyState.style.display = "none";
        };
        testImg.onerror = () => {
            chartImg.style.display = "none";
            emptyState.style.display = "block";
        };
        testImg.src = chartUrl;
    }
}

function renderRegionalTable(data) {
    const tbody = document.querySelector("#regionalTable tbody");
    if (!tbody) return;

    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">No regional data available.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(row => `
        <tr>
            <td><strong>${row.region}</strong></td>
            <td>${Number(row.total_orders).toLocaleString()} orders</td>
            <td>$${Number(row.total_revenue).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
        </tr>
    `).join("");
}

async function loadRawFiles() {
    try {
        const res = await fetch("/api/raw-files");
        const files = await res.json();
        const select = document.getElementById("rawFileSelect");
        if (select && Array.isArray(files)) {
            select.innerHTML = `<option value="">-- All Files in data/raw/ (${files.length} found) --</option>` +
                files.map(f => `<option value="${f}">${f}</option>`).join("");
        }
    } catch (err) {
        console.error("Failed loading raw files:", err);
    }
}

async function loadAuditLogs() {
    try {
        const res = await fetch("/api/audit-logs");
        const logs = await res.json();
        const tbody = document.querySelector("#auditTable tbody");
        if (!tbody) return;

        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No audit logs recorded yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(l => `
            <tr>
                <td>#${l.log_id}</td>
                <td>${l.run_date}</td>
                <td><code>${l.file_name}</code></td>
                <td>${l.records_read}</td>
                <td><span class="badge badge-info">${l.duplicates_removed}</span></td>
                <td><span class="badge badge-success">${l.missing_fixed}</span></td>
                <td><span class="badge badge-danger">${l.invalid_rows}</span></td>
                <td><strong>${l.records_loaded}</strong></td>
                <td><span class="badge ${l.status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">${l.status}</span></td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed loading audit logs:", err);
    }
}

async function loadQuarantineData() {
    try {
        const res = await fetch("/api/quarantine");
        const quarantineFiles = await res.json();
        const tbody = document.querySelector("#quarantineTable tbody");
        const badge = document.getElementById("quarantineBadge");
        if (!tbody) return;

        let allRows = [];
        let totalCount = 0;

        if (Array.isArray(quarantineFiles)) {
            quarantineFiles.forEach(qf => {
                totalCount += qf.row_count;
                if (qf.rows) {
                    qf.rows.forEach(r => {
                        allRows.push({ ...r, _source: qf.file_name });
                    });
                }
            });
        }

        if (badge) badge.textContent = `${totalCount} Fatal Rows Isolated`;

        if (allRows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No quarantined records found.</td></tr>`;
            return;
        }

        tbody.innerHTML = allRows.slice(0, 50).map(r => `
            <tr>
                <td><code>${r._source_file || r._source}</code></td>
                <td>${r.customer_name || 'N/A'} (ID: ${r.customer_id || 'null'})</td>
                <td>${r.product_name || 'N/A'} (ID: ${r.product_id || 'null'})</td>
                <td>${r.sale_date || '<span class="text-muted">missing</span>'}</td>
                <td>${r.quantity || '0'}</td>
                <td>${r.sales_amount || '$0.00'}</td>
                <td><span class="badge badge-danger">${r._rejection_reasons || 'Validation Failure'}</span></td>
            </tr>
        `).join("");
    } catch (err) {
        console.error("Failed loading quarantine data:", err);
    }
}

/* ==========================================================================
   3. Pipeline Execution & Stepper Animation
   ========================================================================== */
function logToConsole(message, type = "info") {
    const consoleEl = document.getElementById("consoleOutput");
    if (!consoleEl) return;

    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = `console-line console-${type}`;
    line.textContent = `[${time}] ${message}`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function setStepState(stepName, state) {
    const el = document.getElementById(`step-${stepName}`);
    if (!el) return;
    el.classList.remove("active", "complete");
    if (state) el.classList.add(state);
}

async function triggerPipeline(targetFile = null) {
    const steps = ["extract", "validate", "transform", "load", "report"];
    steps.forEach(s => setStepState(s, null));

    logToConsole(`Starting ETL pipeline execution${targetFile ? ` for ${targetFile}` : ' on all raw CSV batches'}...`, "info");
    
    // Animate stage 1
    setStepState("extract", "active");
    logToConsole("Reading CSV data, parsing encodings & computing SHA256 hashes...", "info");

    try {
        setStepState("validate", "active");
        setStepState("extract", "complete");
        logToConsole("Executing 6-Point Data Quality Rules (nulls, duplicates, bounds, dates, orphans)...", "info");

        setStepState("transform", "active");
        setStepState("validate", "complete");
        logToConsole("Standardizing casing, trimming whitespace, imputing missing values, and deriving unit_price...", "info");

        const res = await fetch("/api/run-pipeline", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file: targetFile || "" })
        });

        const data = await res.json();

        if (data.success) {
            setStepState("load", "complete");
            setStepState("transform", "complete");
            setStepState("report", "complete");

            logToConsole(`SUCCESS: Pipeline execution complete. Loaded facts into database.`, "success");
            logToConsole(`Audit entry saved to data_quality_log. Cleaned & Quarantine CSVs archived.`, "success");
            
            // Refresh data
            loadDashboardData();
            loadAuditLogs();
            loadQuarantineData();
            loadRawFiles();
        } else {
            logToConsole(`ERROR: ${data.error || 'Pipeline execution failed'}`, "error");
        }
    } catch (err) {
        logToConsole(`NETWORK ERROR: ${err.message}`, "error");
    }
}

/* ==========================================================================
   4. Action Buttons Binding
   ========================================================================== */
function bindActionButtons() {
    // Header Run All
    document.getElementById("btnRunAll")?.addEventListener("click", () => {
        triggerPipeline(null);
    });

    // Run Selected from Tab 2
    document.getElementById("btnRunSelected")?.addEventListener("click", () => {
        const file = document.getElementById("rawFileSelect")?.value;
        triggerPipeline(file || null);
    });

    // Upload CSV (Batch multi-file support)
    document.getElementById("btnUploadCsv")?.addEventListener("click", async () => {
        const fileInput = document.getElementById("csvFileInput");
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            logToConsole("Please select one or more CSV files first.", "warning");
            return;
        }

        const files = Array.from(fileInput.files);
        logToConsole(`Preparing to upload ${files.length} file(s) to data/raw/...`, "info");

        let successCount = 0;
        for (const file of files) {
            try {
                const content = await file.text();
                logToConsole(`Uploading ${file.name}...`, "info");

                const res = await fetch("/api/upload-csv", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filename: file.name, content: content })
                });

                const data = await res.json();
                if (data.success) {
                    successCount++;
                    logToConsole(`Uploaded: ${file.name}`, "success");
                } else {
                    logToConsole(`Failed uploading ${file.name}: ${data.error}`, "error");
                }
            } catch (err) {
                logToConsole(`Error uploading ${file.name}: ${err.message}`, "error");
            }
        }

        logToConsole(`Batch upload finished: ${successCount}/${files.length} file(s) saved to data/raw/.`, "success");
        loadRawFiles();
    });

    // Init DB
    document.getElementById("btnInitDb")?.addEventListener("click", async () => {
        logToConsole("Initializing schema DDL on database...", "info");
        try {
            const res = await fetch("/api/init-db", { method: "POST" });
            const data = await res.json();
            if (data.success) {
                logToConsole("Database schema initialized successfully.", "success");
                checkDatabaseStatus();
            } else {
                logToConsole(`Init DB Error: ${data.error}`, "error");
            }
        } catch (err) {
            logToConsole(`Init DB Request Error: ${err.message}`, "error");
        }
    });

    // Generate Sample Data
    document.getElementById("btnGenData")?.addEventListener("click", async () => {
        logToConsole("Generating synthetic clean monthly & dirty CSV test datasets in data/raw/...", "info");
        try {
            const res = await fetch("/api/generate-data", { method: "POST" });
            const data = await res.json();
            if (data.success) {
                logToConsole("Sample datasets created successfully in data/raw/.", "success");
                loadRawFiles();
            } else {
                logToConsole(`Generate Data Error: ${data.error}`, "error");
            }
        } catch (err) {
            logToConsole(`Generate Data Request Error: ${err.message}`, "error");
        }
    });

    // Refresh buttons
    document.getElementById("btnRefreshChart")?.addEventListener("click", () => loadDashboardData());
    document.getElementById("btnRefreshAudit")?.addEventListener("click", () => {
        loadAuditLogs();
        loadQuarantineData();
    });

    // Clear console
    document.getElementById("btnClearConsole")?.addEventListener("click", () => {
        const consoleEl = document.getElementById("consoleOutput");
        if (consoleEl) consoleEl.innerHTML = `<span class="console-line">[READY] Console cleared.</span>`;
    });
}

/* ==========================================================================
   5. SQL Analytics Studio
   ========================================================================== */
const SQL_PRESETS = {
    "1": `-- 1. Top 10 Customers by Total Revenue
SELECT 
    c.customer_id,
    c.customer_name,
    c.region,
    COUNT(s.sale_id) AS total_orders,
    SUM(s.quantity) AS total_units_sold,
    SUM(s.sales_amount) AS total_revenue,
    ROUND(AVG(s.sales_amount), 2) AS avg_order_value
FROM sales s
INNER JOIN customers c ON s.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY total_revenue DESC
LIMIT 10;`,

    "2": `-- 2. Monthly Sales Trend
SELECT 
    strftime('%Y-%m', s.sale_date) AS sale_month,
    COUNT(s.sale_id) AS transaction_count,
    SUM(s.quantity) AS total_quantity,
    SUM(s.sales_amount) AS total_revenue,
    ROUND(AVG(s.sales_amount), 2) AS avg_ticket_size
FROM sales s
GROUP BY strftime('%Y-%m', s.sale_date)
ORDER BY sale_month ASC;`,

    "3": `-- 3. Sales Breakdown by Region & Share %
SELECT 
    c.region,
    COUNT(DISTINCT c.customer_id) AS active_customers,
    COUNT(s.sale_id) AS order_count,
    SUM(s.sales_amount) AS regional_revenue,
    ROUND(SUM(s.sales_amount) * 100.0 / (SELECT SUM(sales_amount) FROM sales), 2) AS revenue_percentage
FROM sales s
INNER JOIN customers c ON s.customer_id = c.customer_id
GROUP BY c.region
ORDER BY regional_revenue DESC;`,

    "4": `-- 4. Top Products by Category (Window Function: RANK)
WITH category_sales AS (
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        SUM(s.quantity) AS units_sold,
        SUM(s.sales_amount) AS total_sales
    FROM sales s
    INNER JOIN products p ON s.product_id = p.product_id
    GROUP BY p.product_id, p.product_name, p.category
)
SELECT 
    category,
    product_name,
    units_sold,
    total_sales,
    RANK() OVER (PARTITION BY category ORDER BY total_sales DESC) AS rank_in_category
FROM category_sales
ORDER BY category, rank_in_category;`,

    "5": `-- 5. Month-over-Month Growth (CTE + LAG)
WITH monthly_revenue AS (
    SELECT 
        strftime('%Y-%m', sale_date) AS revenue_month,
        SUM(sales_amount) AS monthly_sales
    FROM sales
    GROUP BY strftime('%Y-%m', sale_date)
),
revenue_with_lag AS (
    SELECT 
        revenue_month,
        monthly_sales,
        LAG(monthly_sales, 1) OVER (ORDER BY revenue_month ASC) AS previous_month_sales
    FROM monthly_revenue
)
SELECT 
    revenue_month,
    monthly_sales,
    COALESCE(previous_month_sales, 0) AS previous_month_sales,
    ROUND(monthly_sales - COALESCE(previous_month_sales, monthly_sales), 2) AS absolute_change,
    CASE 
        WHEN previous_month_sales IS NULL OR previous_month_sales = 0 THEN 0.00
        ELSE ROUND(((monthly_sales - previous_month_sales) / previous_month_sales) * 100.0, 2)
    END AS mom_growth_pct
FROM revenue_with_lag
ORDER BY revenue_month ASC;`,

    "6": `-- 6. Customer Cumulative Running Total (Window Function: SUM OVER)
SELECT 
    s.sale_id,
    s.sale_date,
    c.customer_id,
    c.customer_name,
    s.sales_amount,
    SUM(s.sales_amount) OVER (
        PARTITION BY s.customer_id 
        ORDER BY s.sale_date, s.sale_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS customer_cumulative_spend
FROM sales s
INNER JOIN customers c ON s.customer_id = c.customer_id
ORDER BY c.customer_id, s.sale_date, s.sale_id
LIMIT 50;`
};

function initSqlStudio() {
    const select = document.getElementById("sqlPresetSelect");
    const editor = document.getElementById("sqlEditor");
    const execBtn = document.getElementById("btnExecuteSql");

    if (select && editor) {
        editor.value = SQL_PRESETS[select.value] || SQL_PRESETS["4"];

        select.addEventListener("change", () => {
            if (SQL_PRESETS[select.value]) {
                editor.value = SQL_PRESETS[select.value];
            }
        });
    }

    if (execBtn) {
        execBtn.addEventListener("click", async () => {
            const sql = editor?.value?.trim();
            if (!sql) return;

            const metaBadge = document.getElementById("queryMetaBadge");
            if (metaBadge) metaBadge.textContent = "Executing...";

            try {
                const res = await fetch("/api/query", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sql })
                });

                const data = await res.json();
                if (data.success) {
                    if (metaBadge) metaBadge.textContent = `${data.row_count} Rows Returned`;
                    renderQueryResults(data.columns, data.rows);
                } else {
                    if (metaBadge) metaBadge.textContent = "Query Failed";
                    renderQueryError(data.error);
                }
            } catch (err) {
                if (metaBadge) metaBadge.textContent = "Error";
                renderQueryError(err.message);
            }
        });
    }
}

function renderQueryResults(columns, rows) {
    const table = document.getElementById("queryResultTable");
    if (!table) return;

    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");

    thead.innerHTML = `<tr>${columns.map(c => `<th>${c}</th>`).join("")}</tr>`;

    if (!rows || rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${columns.length}" class="text-center text-muted">No records found.</td></tr>`;
        return;
    }

    tbody.innerHTML = rows.map(r => `
        <tr>
            ${columns.map(c => {
                const val = r[c];
                const isNum = typeof val === "number";
                return `<td>${isNum ? val.toLocaleString() : (val !== null ? val : '<span class="text-muted">null</span>')}</td>`;
            }).join("")}
        </tr>
    `).join("");
}

function renderQueryError(errMsg) {
    const table = document.getElementById("queryResultTable");
    if (!table) return;
    table.querySelector("thead").innerHTML = "";
    table.querySelector("tbody").innerHTML = `
        <tr><td class="text-center" style="color: #f43f5e; padding: 20px;">
            ⚠️ Query Error: ${errMsg}
        </td></tr>
    `;
}
