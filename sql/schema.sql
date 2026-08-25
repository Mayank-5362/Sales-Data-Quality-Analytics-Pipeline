-- Customers dimension table
CREATE TABLE IF NOT EXISTS customers (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    region        TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products dimension table
CREATE TABLE IF NOT EXISTS products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sales fact table
CREATE TABLE IF NOT EXISTS sales (
    sale_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    sale_date     TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    sales_amount  NUMERIC NOT NULL,
    source_file   TEXT DEFAULT 'manual',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sales_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    CONSTRAINT fk_sales_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_source ON sales(source_file);

-- Table tracking ingested file hashes to prevent duplicates
CREATE TABLE IF NOT EXISTS processed_files (
    file_hash     TEXT PRIMARY KEY,
    file_name     TEXT NOT NULL,
    row_count     INTEGER NOT NULL,
    loaded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data quality audit log table
CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_name          TEXT NOT NULL,
    records_read       INTEGER NOT NULL DEFAULT 0,
    duplicates_removed INTEGER NOT NULL DEFAULT 0,
    missing_fixed      INTEGER NOT NULL DEFAULT 0,
    invalid_rows       INTEGER NOT NULL DEFAULT 0,
    records_loaded     INTEGER NOT NULL DEFAULT 0,
    status             TEXT DEFAULT 'SUCCESS'
);
