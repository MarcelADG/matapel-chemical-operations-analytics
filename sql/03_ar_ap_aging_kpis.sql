-- Dialect: PostgreSQL
-- Assumes source Excel exports have already been loaded into staging tables with normalized column names and parsed date fields.
--
-- Expected staging tables:
--   staging_sales, staging_purchases, staging_inventory, staging_master_product,
--   staging_ar_aging, staging_ap_aging
--
-- Mirrors src.clean_data.clean_aging plus src.build_features aging summaries.
-- Amount fields follow Python exactly: overdue_amount is outstanding when
-- days_overdue > 0, current_or_future_amount is outstanding when days_overdue
-- <= 0. Only top-overdue document counts filter to positive overdue exposure.

CREATE OR REPLACE VIEW ar_aging_summary_sql AS
WITH normalized_ar AS (
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
fact_ar AS (
    SELECT
        company,
        card_name,
        inv_number,
        days_overdue,
        outstanding,
        CASE
            WHEN days_overdue IS NULL THEN
                CASE LOWER(REPLACE(REPLACE(COALESCE(source_aging_bucket, 'Unknown'), ' ', ''), 'days', ''))
                    WHEN 'current' THEN 'Current'
                    WHEN 'notdue' THEN 'Current'
                    WHEN 'future' THEN 'Current'
                    WHEN '0' THEN 'Current'
                    WHEN '0-0' THEN 'Current'
                    WHEN '1-30' THEN '1-30'
                    WHEN '1to30' THEN '1-30'
                    WHEN '0-30' THEN '1-30'
                    WHEN '31-60' THEN '31-60'
                    WHEN '31to60' THEN '31-60'
                    WHEN '61-90' THEN '61-90'
                    WHEN '61to90' THEN '61-90'
                    WHEN '90+' THEN '90+'
                    WHEN '>90' THEN '90+'
                    WHEN '91+' THEN '90+'
                    WHEN '91plus' THEN '90+'
                    WHEN 'over90' THEN '90+'
                    ELSE COALESCE(source_aging_bucket, 'Unknown')
                END
            WHEN days_overdue <= 0 THEN 'Current'
            WHEN days_overdue BETWEEN 1 AND 30 THEN '1-30'
            WHEN days_overdue BETWEEN 31 AND 60 THEN '31-60'
            WHEN days_overdue BETWEEN 61 AND 90 THEN '61-90'
            WHEN days_overdue > 90 THEN '90+'
        END AS aging_bucket,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS is_overdue,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN 0
            ELSE outstanding
        END AS current_or_future_amount,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN outstanding
            ELSE 0
        END AS overdue_amount
    FROM normalized_ar
),
ordered_ar AS (
    SELECT
        *,
        CASE aging_bucket
            WHEN 'Current' THEN 0
            WHEN '1-30' THEN 1
            WHEN '31-60' THEN 2
            WHEN '61-90' THEN 3
            WHEN '90+' THEN 4
            ELSE 5
        END AS aging_bucket_order,
        CASE WHEN COALESCE(outstanding, 0) > 0 THEN inv_number END AS outstanding_document,
        CASE WHEN COALESCE(outstanding, 0) > 0 THEN card_name END AS outstanding_counterparty
    FROM fact_ar
)
SELECT
    company,
    aging_bucket,
    SUM(outstanding) AS outstanding,
    SUM(overdue_amount) AS overdue_amount,
    SUM(current_or_future_amount) AS current_or_future_amount,
    COUNT(DISTINCT outstanding_document) AS document_count,
    COUNT(DISTINCT outstanding_counterparty) AS counterparty_count,
    COUNT(*) AS record_count,
    'AR' AS "table"
FROM ordered_ar
GROUP BY company, aging_bucket_order, aging_bucket
ORDER BY aging_bucket_order, company;

CREATE OR REPLACE VIEW ap_aging_summary_sql AS
WITH normalized_ap AS (
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
fact_ap AS (
    SELECT
        company,
        card_name,
        inv_number,
        days_overdue,
        outstanding,
        CASE
            WHEN days_overdue IS NULL THEN
                CASE LOWER(REPLACE(REPLACE(COALESCE(source_aging_bucket, 'Unknown'), ' ', ''), 'days', ''))
                    WHEN 'current' THEN 'Current'
                    WHEN 'notdue' THEN 'Current'
                    WHEN 'future' THEN 'Current'
                    WHEN '0' THEN 'Current'
                    WHEN '0-0' THEN 'Current'
                    WHEN '1-30' THEN '1-30'
                    WHEN '1to30' THEN '1-30'
                    WHEN '0-30' THEN '1-30'
                    WHEN '31-60' THEN '31-60'
                    WHEN '31to60' THEN '31-60'
                    WHEN '61-90' THEN '61-90'
                    WHEN '61to90' THEN '61-90'
                    WHEN '90+' THEN '90+'
                    WHEN '>90' THEN '90+'
                    WHEN '91+' THEN '90+'
                    WHEN '91plus' THEN '90+'
                    WHEN 'over90' THEN '90+'
                    ELSE COALESCE(source_aging_bucket, 'Unknown')
                END
            WHEN days_overdue <= 0 THEN 'Current'
            WHEN days_overdue BETWEEN 1 AND 30 THEN '1-30'
            WHEN days_overdue BETWEEN 31 AND 60 THEN '31-60'
            WHEN days_overdue BETWEEN 61 AND 90 THEN '61-90'
            WHEN days_overdue > 90 THEN '90+'
        END AS aging_bucket,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS is_overdue,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN 0
            ELSE outstanding
        END AS current_or_future_amount,
        CASE
            WHEN COALESCE(days_overdue, 0) > 0 THEN outstanding
            ELSE 0
        END AS overdue_amount
    FROM normalized_ap
),
ordered_ap AS (
    SELECT
        *,
        CASE aging_bucket
            WHEN 'Current' THEN 0
            WHEN '1-30' THEN 1
            WHEN '31-60' THEN 2
            WHEN '61-90' THEN 3
            WHEN '90+' THEN 4
            ELSE 5
        END AS aging_bucket_order,
        CASE WHEN COALESCE(outstanding, 0) > 0 THEN inv_number END AS outstanding_document,
        CASE WHEN COALESCE(outstanding, 0) > 0 THEN card_name END AS outstanding_counterparty
    FROM fact_ap
)
SELECT
    company,
    aging_bucket,
    SUM(outstanding) AS outstanding,
    SUM(overdue_amount) AS overdue_amount,
    SUM(current_or_future_amount) AS current_or_future_amount,
    COUNT(DISTINCT outstanding_document) AS document_count,
    COUNT(DISTINCT outstanding_counterparty) AS counterparty_count,
    COUNT(*) AS record_count,
    'AP' AS "table"
FROM ordered_ap
GROUP BY company, aging_bucket_order, aging_bucket
ORDER BY aging_bucket_order, company;

CREATE OR REPLACE VIEW top_customers_overdue_ar_sql AS
WITH normalized_ar AS (
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
overdue AS (
    SELECT
        company,
        card_name AS customer,
        inv_number,
        outstanding AS overdue_amount,
        outstanding,
        days_overdue
    FROM normalized_ar
    WHERE COALESCE(days_overdue, 0) > 0
      AND COALESCE(outstanding, 0) > 0
)
SELECT
    company,
    customer,
    SUM(overdue_amount) AS overdue_amount,
    SUM(outstanding) AS outstanding,
    MAX(days_overdue) AS max_days_overdue,
    COUNT(DISTINCT inv_number) AS overdue_documents
FROM overdue
GROUP BY company, customer
ORDER BY company, overdue_amount DESC;

CREATE OR REPLACE VIEW top_suppliers_overdue_ap_sql AS
WITH normalized_ap AS (
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
overdue AS (
    SELECT
        company,
        card_name AS supplier,
        inv_number,
        outstanding AS overdue_amount,
        outstanding,
        days_overdue
    FROM normalized_ap
    WHERE COALESCE(days_overdue, 0) > 0
      AND COALESCE(outstanding, 0) > 0
)
SELECT
    company,
    supplier,
    SUM(overdue_amount) AS overdue_amount,
    SUM(outstanding) AS outstanding,
    MAX(days_overdue) AS max_days_overdue,
    COUNT(DISTINCT inv_number) AS overdue_documents
FROM overdue
GROUP BY company, supplier
ORDER BY company, overdue_amount DESC;
