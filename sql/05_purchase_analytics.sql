-- Dialect: PostgreSQL
-- Assumes source Excel exports have already been loaded into staging tables with normalized column names and parsed date fields.
--
-- Expected staging tables:
--   staging_sales, staging_purchases, staging_inventory, staging_master_product,
--   staging_ar_aging, staging_ap_aging
--
-- Mirrors src.clean_data.clean_purchases and src.build_features.build_purchase_summary.
-- The Python pipeline uses simple AVG(price_usd) for average purchase price,
-- not a weighted average. Lead time and delivery delay metrics are calculated
-- only when actual delivery dates are available.

CREATE OR REPLACE VIEW purchase_supplier_product_sql AS
WITH normalized_purchases AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        NULLIF(BTRIM(po_number::text), '')::numeric AS po_number,
        doc_date::date AS doc_date,
        expected_deliv_date::date AS expected_deliv_date,
        actual_deliv_date::date AS actual_deliv_date,
        NULLIF(BTRIM(card_name::text), '') AS card_name,
        NULLIF(BTRIM(itms_grp_nam::text), '') AS itms_grp_nam,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(doc_currency::text), '') AS doc_currency,
        NULLIF(BTRIM(doc_price::text), '')::numeric AS doc_price,
        NULLIF(BTRIM(doc_rate::text), '')::numeric AS doc_rate,
        NULLIF(BTRIM(exc_rate::text), '')::numeric AS exc_rate,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd
    FROM staging_purchases
),
fact_purchases AS (
    SELECT
        company,
        card_name,
        COALESCE(item_category, itms_grp_nam, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, itms_grp_nam, 'Unknown') AS product_line,
        item_code,
        quantity,
        price_usd,
        CASE
            WHEN actual_deliv_date IS NOT NULL AND doc_date IS NOT NULL
                THEN actual_deliv_date - doc_date
        END AS purchase_lead_time_days,
        CASE
            WHEN actual_deliv_date IS NOT NULL AND expected_deliv_date IS NOT NULL
                THEN actual_deliv_date - expected_deliv_date
        END AS delivery_delay_days,
        actual_deliv_date IS NOT NULL AS has_actual_delivery_date,
        COALESCE(
            actual_deliv_date IS NOT NULL
            AND (actual_deliv_date - expected_deliv_date) > 0,
            FALSE
        ) AS is_late_delivery
    FROM normalized_purchases
)
SELECT
    company,
    card_name,
    product_family,
    product_line,
    SUM(quantity) AS purchase_quantity,
    AVG(price_usd) AS avg_purchase_price_usd,
    COUNT(*) AS po_lines,
    SUM(CASE WHEN has_actual_delivery_date THEN 1 ELSE 0 END) AS delivery_metric_records,
    AVG(purchase_lead_time_days) AS avg_lead_time_days,
    AVG(delivery_delay_days) AS avg_delivery_delay_days,
    SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END) AS late_delivery_count
FROM fact_purchases
GROUP BY company, card_name, product_family, product_line
ORDER BY company, late_delivery_count DESC, purchase_quantity DESC;

CREATE OR REPLACE VIEW purchase_price_trend_sql AS
WITH normalized_purchases AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        NULLIF(BTRIM(po_number::text), '')::numeric AS po_number,
        doc_date::date AS doc_date,
        expected_deliv_date::date AS expected_deliv_date,
        actual_deliv_date::date AS actual_deliv_date,
        NULLIF(BTRIM(card_name::text), '') AS card_name,
        NULLIF(BTRIM(itms_grp_nam::text), '') AS itms_grp_nam,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(doc_currency::text), '') AS doc_currency,
        NULLIF(BTRIM(doc_price::text), '')::numeric AS doc_price,
        NULLIF(BTRIM(doc_rate::text), '')::numeric AS doc_rate,
        NULLIF(BTRIM(exc_rate::text), '')::numeric AS exc_rate,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd
    FROM staging_purchases
),
fact_purchases AS (
    SELECT
        company,
        DATE_TRUNC('month', doc_date)::date AS month,
        COALESCE(item_category, itms_grp_nam, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, itms_grp_nam, 'Unknown') AS product_line,
        item_code,
        quantity,
        price_usd
    FROM normalized_purchases
)
SELECT
    company,
    month,
    product_family,
    product_line,
    SUM(quantity) AS purchase_quantity,
    AVG(price_usd) AS avg_purchase_price_usd,
    COUNT(*) AS po_lines
FROM fact_purchases
WHERE month IS NOT NULL
GROUP BY company, month, product_family, product_line
ORDER BY company, product_line, month;

CREATE OR REPLACE VIEW late_delivery_categories_sql AS
WITH normalized_purchases AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        NULLIF(BTRIM(po_number::text), '')::numeric AS po_number,
        doc_date::date AS doc_date,
        expected_deliv_date::date AS expected_deliv_date,
        actual_deliv_date::date AS actual_deliv_date,
        NULLIF(BTRIM(card_name::text), '') AS card_name,
        NULLIF(BTRIM(itms_grp_nam::text), '') AS itms_grp_nam,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(quantity::text), '')::numeric AS quantity,
        NULLIF(BTRIM(doc_currency::text), '') AS doc_currency,
        NULLIF(BTRIM(doc_price::text), '')::numeric AS doc_price,
        NULLIF(BTRIM(doc_rate::text), '')::numeric AS doc_rate,
        NULLIF(BTRIM(exc_rate::text), '')::numeric AS exc_rate,
        NULLIF(BTRIM(price_usd::text), '')::numeric AS price_usd
    FROM staging_purchases
),
fact_purchases AS (
    SELECT
        company,
        card_name,
        COALESCE(item_category, itms_grp_nam, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, itms_grp_nam, 'Unknown') AS product_line,
        CASE
            WHEN actual_deliv_date IS NOT NULL AND expected_deliv_date IS NOT NULL
                THEN actual_deliv_date - expected_deliv_date
        END AS delivery_delay_days,
        COALESCE(
            actual_deliv_date IS NOT NULL
            AND (actual_deliv_date - expected_deliv_date) > 0,
            FALSE
        ) AS is_late_delivery
    FROM normalized_purchases
)
SELECT
    company,
    card_name,
    product_family,
    product_line,
    SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END) AS late_delivery_count,
    AVG(delivery_delay_days) AS avg_delay_days,
    MAX(delivery_delay_days) AS max_delay_days
FROM fact_purchases
WHERE is_late_delivery
GROUP BY company, card_name, product_family, product_line
ORDER BY company, late_delivery_count DESC, avg_delay_days DESC;
