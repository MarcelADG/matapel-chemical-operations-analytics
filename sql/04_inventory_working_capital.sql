-- Dialect: PostgreSQL
-- Assumes source Excel exports have already been loaded into staging tables with normalized column names and parsed date fields.
--
-- Expected staging tables:
--   staging_sales, staging_purchases, staging_inventory, staging_master_product,
--   staging_ar_aging, staging_ap_aging
--
-- Mirrors src.build_features.build_monthly_inventory_summary and
-- src.kpis.build_working_capital_kpis. Inventory is treated as a movement/value
-- export, not an audited month-end inventory snapshot; DIO remains approximate.

CREATE OR REPLACE VIEW monthly_inventory_summary_sql AS
WITH normalized_inventory AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        movement_date::date AS movement_date,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(warehouse::text), '') AS warehouse,
        NULLIF(BTRIM(on_hand_qty::text), '')::numeric AS on_hand_qty,
        NULLIF(BTRIM(map_cost::text), '')::numeric AS map_cost,
        NULLIF(BTRIM(trans_value::text), '')::numeric AS trans_value
    FROM staging_inventory
),
fact_inventory AS (
    SELECT
        company,
        movement_date,
        DATE_TRUNC('month', movement_date)::date AS month,
        COALESCE(item_category, item_group, 'Unknown') AS product_family,
        COALESCE(parent_name, item_category, item_group, 'Unknown') AS product_line,
        item_code,
        warehouse,
        on_hand_qty,
        map_cost,
        on_hand_qty * map_cost AS inventory_value_idr,
        on_hand_qty < 0 AS is_negative_inventory,
        COALESCE(on_hand_qty, 0) = 0 AS is_zero_inventory,
        on_hand_qty * map_cost < 0 AS is_negative_value
    FROM normalized_inventory
),
monthly AS (
    SELECT
        company,
        month,
        product_family,
        product_line,
        warehouse,
        SUM(on_hand_qty) AS on_hand_qty,
        SUM(inventory_value_idr) AS inventory_value_idr,
        AVG(map_cost) AS avg_map_cost,
        COUNT(DISTINCT item_code) AS item_count,
        SUM(CASE WHEN is_negative_inventory THEN 1 ELSE 0 END) AS negative_inventory_lines,
        SUM(CASE WHEN is_zero_inventory THEN 1 ELSE 0 END) AS zero_inventory_lines,
        SUM(CASE WHEN is_negative_value THEN 1 ELSE 0 END) AS negative_value_lines
    FROM fact_inventory
    WHERE month IS NOT NULL
    GROUP BY company, month, product_family, product_line, warehouse
),
latest_month AS (
    SELECT MAX(month) AS month
    FROM monthly
),
latest_thresholds AS (
    SELECT
        PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY inventory_value_idr) AS high_value_threshold,
        PERCENTILE_CONT(0.2) WITHIN GROUP (ORDER BY on_hand_qty) AS low_quantity_threshold
    FROM monthly
    WHERE month = (SELECT month FROM latest_month)
)
SELECT
    monthly.company,
    monthly.month,
    monthly.product_family,
    monthly.product_line,
    monthly.warehouse,
    monthly.on_hand_qty,
    monthly.inventory_value_idr,
    monthly.avg_map_cost,
    monthly.item_count,
    monthly.negative_inventory_lines,
    monthly.zero_inventory_lines,
    monthly.negative_value_lines,
    CASE
        WHEN latest_thresholds.high_value_threshold IS NULL THEN FALSE
        ELSE COALESCE(monthly.inventory_value_idr >= latest_thresholds.high_value_threshold, FALSE)
    END AS is_high_value_inventory,
    CASE
        WHEN latest_thresholds.high_value_threshold IS NULL OR latest_thresholds.low_quantity_threshold IS NULL THEN FALSE
        ELSE COALESCE(monthly.month = latest_month.month
            AND monthly.inventory_value_idr >= latest_thresholds.high_value_threshold
            AND monthly.on_hand_qty <= latest_thresholds.low_quantity_threshold, FALSE)
    END AS is_slow_moving_indicator
FROM monthly
CROSS JOIN latest_month
CROSS JOIN latest_thresholds
ORDER BY company, month, product_line, warehouse;

CREATE OR REPLACE VIEW inventory_value_by_product_line_sql AS
WITH monthly_inventory AS (
    SELECT *
    FROM monthly_inventory_summary_sql
),
latest_month AS (
    SELECT MAX(month) AS month
    FROM monthly_inventory
)
SELECT
    product_line,
    SUM(inventory_value_idr) AS inventory_value_idr
FROM monthly_inventory
WHERE month = (SELECT month FROM latest_month)
GROUP BY product_line
ORDER BY inventory_value_idr DESC NULLS LAST;

CREATE OR REPLACE VIEW working_capital_kpis_sql AS
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
        inv_date,
        total_idr,
        quantity * moving_avg_cost AS cogs_idr
    FROM normalized_sales
),
sales_period AS (
    SELECT
        MIN(inv_date) AS period_start,
        MAX(inv_date) AS period_end,
        GREATEST(1, (MAX(inv_date)::date - MIN(inv_date)::date) + 1) AS period_days,
        SUM(total_idr) AS revenue_idr,
        SUM(cogs_idr) AS cogs_idr
    FROM fact_sales
),
normalized_inventory AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        movement_date::date AS movement_date,
        NULLIF(BTRIM(item_group::text), '') AS item_group,
        NULLIF(BTRIM(item_category::text), '') AS item_category,
        NULLIF(BTRIM(parent_code::text), '') AS parent_code,
        NULLIF(BTRIM(parent_name::text), '') AS parent_name,
        NULLIF(BTRIM(item_code::text), '') AS item_code,
        NULLIF(BTRIM(item_name::text), '') AS item_name,
        NULLIF(BTRIM(warehouse::text), '') AS warehouse,
        NULLIF(BTRIM(on_hand_qty::text), '')::numeric AS on_hand_qty,
        NULLIF(BTRIM(map_cost::text), '')::numeric AS map_cost,
        NULLIF(BTRIM(trans_value::text), '')::numeric AS trans_value
    FROM staging_inventory
),
inventory_monthly AS (
    SELECT
        DATE_TRUNC('month', movement_date)::date AS month,
        SUM(on_hand_qty * map_cost) AS month_inventory_value_idr
    FROM normalized_inventory
    WHERE movement_date IS NOT NULL
    GROUP BY DATE_TRUNC('month', movement_date)::date
),
inventory_balance AS (
    SELECT
        COALESCE(AVG(month_inventory_value_idr), 0) AS average_inventory_idr
    FROM inventory_monthly
),
normalized_ar AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        NULLIF(BTRIM(card_name::text), '') AS card_name,
        NULLIF(BTRIM(inv_number::text), '') AS inv_number,
        inv_date::date AS inv_date,
        inv_due_date::date AS inv_due_date,
        payment_date_1::date AS payment_date_1,
        payment_date_2::date AS payment_date_2,
        NULLIF(BTRIM(pymnt_group::text), '') AS pymnt_group,
        NULLIF(BTRIM(extra_days::text), '')::numeric AS extra_days,
        NULLIF(BTRIM(days_overdue::text), '')::numeric AS days_overdue,
        NULLIF(BTRIM(aging_bucket::text), '') AS source_aging_bucket,
        NULLIF(BTRIM(doc_total::text), '')::numeric AS doc_total,
        NULLIF(BTRIM(paid_to_date::text), '')::numeric AS paid_to_date,
        NULLIF(BTRIM(outstanding::text), '')::numeric AS outstanding
    FROM staging_ar_aging
),
ar_balance AS (
    SELECT
        SUM(outstanding) AS total_ar_outstanding,
        SUM(CASE WHEN COALESCE(days_overdue, 0) > 0 THEN outstanding ELSE 0 END) AS overdue_ar,
        SUM(CASE WHEN COALESCE(days_overdue, 0) > 0 THEN 0 ELSE outstanding END) AS current_or_future_ar
    FROM normalized_ar
),
normalized_ap AS (
    SELECT DISTINCT
        NULLIF(BTRIM(company::text), '') AS company,
        NULLIF(BTRIM(card_name::text), '') AS card_name,
        NULLIF(BTRIM(inv_number::text), '') AS inv_number,
        inv_date::date AS inv_date,
        inv_due_date::date AS inv_due_date,
        payment_date_1::date AS payment_date_1,
        payment_date_2::date AS payment_date_2,
        NULLIF(BTRIM(pymnt_group::text), '') AS pymnt_group,
        NULLIF(BTRIM(extra_days::text), '')::numeric AS extra_days,
        NULLIF(BTRIM(days_overdue::text), '')::numeric AS days_overdue,
        NULLIF(BTRIM(aging_bucket::text), '') AS source_aging_bucket,
        NULLIF(BTRIM(doc_total::text), '')::numeric AS doc_total,
        NULLIF(BTRIM(paid_to_date::text), '')::numeric AS paid_to_date,
        NULLIF(BTRIM(outstanding::text), '')::numeric AS outstanding
    FROM staging_ap_aging
),
ap_balance AS (
    SELECT
        SUM(outstanding) AS total_ap_outstanding,
        SUM(CASE WHEN COALESCE(days_overdue, 0) > 0 THEN outstanding ELSE 0 END) AS overdue_ap,
        SUM(CASE WHEN COALESCE(days_overdue, 0) > 0 THEN 0 ELSE outstanding END) AS current_or_future_ap
    FROM normalized_ap
)
SELECT
    sales_period.period_start,
    sales_period.period_end,
    COALESCE(sales_period.period_days, 365) AS period_days,
    sales_period.revenue_idr,
    sales_period.cogs_idr,
    inventory_balance.average_inventory_idr,
    COALESCE(ar_balance.total_ar_outstanding, 0) AS total_ar_outstanding,
    COALESCE(ap_balance.total_ap_outstanding, 0) AS total_ap_outstanding,
    COALESCE(ar_balance.overdue_ar, 0) AS overdue_ar,
    COALESCE(ap_balance.overdue_ap, 0) AS overdue_ap,
    COALESCE(ar_balance.current_or_future_ar, 0) AS current_or_future_ar,
    COALESCE(ap_balance.current_or_future_ap, 0) AS current_or_future_ap,
    CASE
        WHEN sales_period.revenue_idr = 0 THEN NULL
        ELSE COALESCE(ar_balance.total_ar_outstanding, 0) / sales_period.revenue_idr * COALESCE(sales_period.period_days, 365)
    END AS dso_days,
    CASE
        WHEN sales_period.cogs_idr = 0 THEN NULL
        ELSE COALESCE(ap_balance.total_ap_outstanding, 0) / sales_period.cogs_idr * COALESCE(sales_period.period_days, 365)
    END AS dpo_days,
    CASE
        WHEN sales_period.cogs_idr = 0 THEN NULL
        ELSE inventory_balance.average_inventory_idr / sales_period.cogs_idr * COALESCE(sales_period.period_days, 365)
    END AS dio_days,
    (
        CASE
            WHEN sales_period.cogs_idr = 0 THEN NULL
            ELSE inventory_balance.average_inventory_idr / sales_period.cogs_idr * COALESCE(sales_period.period_days, 365)
        END
        + CASE
            WHEN sales_period.revenue_idr = 0 THEN NULL
            ELSE COALESCE(ar_balance.total_ar_outstanding, 0) / sales_period.revenue_idr * COALESCE(sales_period.period_days, 365)
        END
        - CASE
            WHEN sales_period.cogs_idr = 0 THEN NULL
            ELSE COALESCE(ap_balance.total_ap_outstanding, 0) / sales_period.cogs_idr * COALESCE(sales_period.period_days, 365)
        END
    ) AS cash_conversion_cycle_days,
    'AR/AP are aging snapshot balances; DIO is an approximate indicator from available inventory movement/value records; COGS is estimated from moving average cost.' AS assumption
FROM sales_period
CROSS JOIN inventory_balance
CROSS JOIN ar_balance
CROSS JOIN ap_balance;
