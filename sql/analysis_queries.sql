-- 1. Top 10 Customers by Revenue
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
LIMIT 10;

-- 2. Monthly Sales Trend
SELECT 
    strftime('%Y-%m', s.sale_date) AS sale_month,
    COUNT(s.sale_id) AS transaction_count,
    SUM(s.quantity) AS total_quantity,
    SUM(s.sales_amount) AS total_revenue,
    ROUND(AVG(s.sales_amount), 2) AS avg_ticket_size
FROM sales s
GROUP BY strftime('%Y-%m', s.sale_date)
ORDER BY sale_month ASC;

-- 3. Sales Breakdown by Region
SELECT 
    c.region,
    COUNT(DISTINCT c.customer_id) AS active_customers,
    COUNT(s.sale_id) AS order_count,
    SUM(s.sales_amount) AS regional_revenue,
    ROUND(SUM(s.sales_amount) * 100.0 / (SELECT SUM(sales_amount) FROM sales), 2) AS revenue_percentage
FROM sales s
INNER JOIN customers c ON s.customer_id = c.customer_id
GROUP BY c.region
ORDER BY regional_revenue DESC;

-- 4. Top Products by Category with Rank
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
ORDER BY category, rank_in_category;

-- 5. Month over Month Revenue Growth
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
ORDER BY revenue_month ASC;

-- 6. Customer Cumulative Running Total
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
ORDER BY c.customer_id, s.sale_date, s.sale_id;
