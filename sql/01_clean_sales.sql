-- Dialect: PostgreSQL
-- Assumes source Excel exports have already been loaded into staging tables with normalized column names and parsed date fields.
--
-- Expected staging tables:
--   staging_sales, staging_purchases, staging_inventory, staging_master_product,
--   staging_ar_aging, staging_ap_aging
--
-- Mirrors src.clean_data.clean_sales.
-- SalesHist has no invoice number, so this view only removes exact duplicate
-- normalized rows. It does not infer duplicates from partial business keys.

CREATE OR REPLACE VIEW fact_sales_sql AS
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
cleaned_sales AS (
    SELECT
        company,
        inv_date,
        cust_name,
        item_group,
        item_category,
        parent_code,
        parent_name,
        item_code,
        item_name,
        quantity,
        price_usd,
        total_usd,
        price_idr,
        total_idr,
        moving_avg_cost,
        COALESCE(item_category, item_group, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        DATE_TRUNC('month', inv_date)::date AS month
    FROM normalized_sales
)
SELECT
    company,
    inv_date,
    cust_name,
    item_group,
    item_category,
    parent_code,
    parent_name,
    item_code,
    item_name,
    quantity,
    price_usd,
    total_usd,
    price_idr,
    total_idr,
    moving_avg_cost,
    product_family,
    product_line,
    month,
    quantity * moving_avg_cost AS cogs_idr,
    total_idr - (quantity * moving_avg_cost) AS gross_profit_idr,
    CASE
        WHEN total_idr IS NULL OR total_idr = 0 THEN NULL
        ELSE (total_idr - (quantity * moving_avg_cost)) / total_idr
    END AS gross_margin_pct
FROM cleaned_sales;
