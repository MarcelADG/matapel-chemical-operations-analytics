-- Dialect: PostgreSQL
-- Assumes source Excel exports have already been loaded into staging tables with normalized column names and parsed date fields.
--
-- Expected staging tables:
--   staging_sales, staging_purchases, staging_inventory, staging_master_product,
--   staging_ar_aging, staging_ap_aging
--
-- Mirrors src.build_features sales tables. No missing calendar months are
-- created here because the Python pipeline does not create a month spine.

CREATE OR REPLACE VIEW monthly_sales_summary_sql AS
WITH normalized_sales AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        inv_date::date AS inv_date,
        NULLIF(BTRIM(cust_name::text), '') AS cust_name,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd,
        NULLIF(BTRIM(total_usd::text), '')::numeric AS total_usd,
        NULLIF(BTRIM(price_idr::text), '')::numeric AS price_idr,
        NULLIF(BTRIM(total_idr::text), '')::numeric AS total_idr,
        NULLIF(BTRIM(moving_avg_cost::text), '')::numeric AS moving_avg_cost
    FROM staging_sales
),
fact_sales AS (
    SELECT
        company,
        inv_date,
        DATE_TRUNC('month', inv_date)::date AS month,
        cust_name,
        item_code,
        COALESCE(item_category, item_group, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        quantity,
        total_usd,
        total_idr,
        quantity * moving_avg_cost AS cogs_idr,
        total_idr - (quantity * moving_avg_cost) AS gross_profit_idr
    FROM normalized_sales
),
monthly AS (
    SELECT
        company,
        month,
        SUM(quantity) AS quantity_sold,
        SUM(total_usd) AS revenue_usd,
        SUM(total_idr) AS revenue_idr,
        SUM(cogs_idr) AS cogs_idr,
        SUM(gross_profit_idr) AS gross_profit_idr,
        COUNT(DISTINCT cust_name) AS customer_count,
        COUNT(DISTINCT product_line) AS product_line_count,
        COUNT(*) AS invoice_line_count
    FROM fact_sales
    WHERE month IS NOT NULL
    GROUP BY company, month
)
SELECT
    company,
    month,
    quantity_sold,
    revenue_usd,
    revenue_idr,
    cogs_idr,
    gross_profit_idr,
    customer_count,
    product_line_count,
    invoice_line_count,
    CASE WHEN quantity_sold = 0 THEN NULL ELSE revenue_idr / quantity_sold END AS avg_selling_price_idr,
    CASE WHEN revenue_idr = 0 THEN NULL ELSE gross_profit_idr / revenue_idr END AS gross_margin_pct
FROM monthly
ORDER BY company, month;

CREATE OR REPLACE VIEW monthly_product_sales_sql AS
WITH normalized_sales AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        inv_date::date AS inv_date,
        NULLIF(BTRIM(cust_name::text), '') AS cust_name,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd,
        NULLIF(BTRIM(total_usd::text), '')::numeric AS total_usd,
        NULLIF(BTRIM(price_idr::text), '')::numeric AS price_idr,
        NULLIF(BTRIM(total_idr::text), '')::numeric AS total_idr,
        NULLIF(BTRIM(moving_avg_cost::text), '')::numeric AS moving_avg_cost
    FROM staging_sales
),
fact_sales AS (
    SELECT
        company,
        DATE_TRUNC('month', inv_date)::date AS month,
        COALESCE(item_category, item_group, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        quantity,
        total_usd,
        total_idr,
        quantity * moving_avg_cost AS cogs_idr,
        total_idr - (quantity * moving_avg_cost) AS gross_profit_idr
    FROM normalized_sales
),
monthly AS (
    SELECT
        company,
        month,
        product_family,
        product_line,
        SUM(quantity) AS quantity_sold,
        SUM(total_usd) AS revenue_usd,
        SUM(total_idr) AS revenue_idr,
        SUM(cogs_idr) AS cogs_idr,
        SUM(gross_profit_idr) AS gross_profit_idr,
        COUNT(*) AS invoice_count
    FROM fact_sales
    WHERE month IS NOT NULL
    GROUP BY company, month, product_family, product_line
)
SELECT
    company,
    month,
    product_family,
    product_line,
    quantity_sold,
    revenue_usd,
    revenue_idr,
    cogs_idr,
    gross_profit_idr,
    invoice_count,
    CASE WHEN quantity_sold = 0 THEN NULL ELSE revenue_idr / quantity_sold END AS avg_selling_price_idr,
    CASE WHEN revenue_idr = 0 THEN NULL ELSE gross_profit_idr / revenue_idr END AS gross_margin_pct
FROM monthly
ORDER BY company, month, product_line;

CREATE OR REPLACE VIEW product_line_performance_sql AS
WITH normalized_sales AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        inv_date::date AS inv_date,
        NULLIF(BTRIM(cust_name::text), '') AS cust_name,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd,
        NULLIF(BTRIM(total_usd::text), '')::numeric AS total_usd,
        NULLIF(BTRIM(price_idr::text), '')::numeric AS price_idr,
        NULLIF(BTRIM(total_idr::text), '')::numeric AS total_idr,
        NULLIF(BTRIM(moving_avg_cost::text), '')::numeric AS moving_avg_cost
    FROM staging_sales
),
fact_sales AS (
    SELECT
        company,
        DATE_TRUNC('month', inv_date)::date AS month,
        cust_name,
        COALESCE(item_category, item_group, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        quantity,
        total_usd,
        total_idr,
        quantity * moving_avg_cost AS cogs_idr,
        total_idr - (quantity * moving_avg_cost) AS gross_profit_idr
    FROM normalized_sales
),
product_line_base AS (
    SELECT
        company,
        product_family,
        product_line,
        SUM(quantity) AS quantity_sold,
        SUM(total_usd) AS revenue_usd,
        SUM(total_idr) AS revenue_idr,
        SUM(cogs_idr) AS cogs_idr,
        SUM(gross_profit_idr) AS gross_profit_idr,
        COUNT(DISTINCT cust_name) AS customer_count,
        COUNT(DISTINCT month) AS active_months
    FROM fact_sales
    GROUP BY company, product_family, product_line
),
ranked AS (
    SELECT
        company,
        product_family,
        product_line,
        quantity_sold,
        revenue_usd,
        revenue_idr,
        cogs_idr,
        gross_profit_idr,
        customer_count,
        active_months,
        CASE WHEN quantity_sold = 0 THEN NULL ELSE revenue_idr / quantity_sold END AS avg_selling_price_idr,
        CASE WHEN revenue_idr = 0 THEN NULL ELSE gross_profit_idr / revenue_idr END AS gross_margin_pct,
        DENSE_RANK() OVER (
            PARTITION BY company
            ORDER BY revenue_idr DESC NULLS LAST
        ) AS revenue_rank,
        DENSE_RANK() OVER (
            PARTITION BY company
            ORDER BY quantity_sold DESC NULLS LAST
        ) AS quantity_rank
    FROM product_line_base
)
SELECT
    company,
    product_family,
    product_line,
    quantity_sold,
    revenue_usd,
    revenue_idr,
    cogs_idr,
    gross_profit_idr,
    customer_count,
    active_months,
    avg_selling_price_idr,
    gross_margin_pct,
    revenue_rank,
    quantity_rank
FROM ranked
ORDER BY company, revenue_rank, product_line;

CREATE OR REPLACE VIEW customer_performance_sql AS
WITH normalized_sales AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        inv_date::date AS inv_date,
        NULLIF(BTRIM(cust_name::text), '') AS cust_name,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd,
        NULLIF(BTRIM(total_usd::text), '')::numeric AS total_usd,
        NULLIF(BTRIM(price_idr::text), '')::numeric AS price_idr,
        NULLIF(BTRIM(total_idr::text), '')::numeric AS total_idr,
        NULLIF(BTRIM(moving_avg_cost::text), '')::numeric AS moving_avg_cost
    FROM staging_sales
),
fact_sales AS (
    SELECT
        company,
        cust_name,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        item_code,
        quantity,
        total_usd,
        total_idr
    FROM normalized_sales
)
SELECT
    company,
    cust_name,
    SUM(total_idr) AS revenue_idr,
    SUM(total_usd) AS revenue_usd,
    SUM(quantity) AS quantity_sold,
    COUNT(DISTINCT product_line) AS product_lines,
    COUNT(*) AS invoice_lines
FROM fact_sales
GROUP BY company, cust_name
ORDER BY company, revenue_idr DESC;
