# Executive Summary

This project builds a reproducible operations analytics pipeline for SAP-style Excel exports covering sales, purchasing, inventory, AR aging, AP aging, and working capital.

## Scope

The pipeline creates cleaned fact/dimension tables, monthly reporting tables, data-quality checks, demand forecasts, PNG charts, and an Excel dashboard workbook. Public sample data is synthetic and mirrors the source schema without exposing proprietary customer, supplier, product, or transaction details.

## Business Questions

- Which chemical product families and product lines drive revenue, volume, and estimated gross profit?
- Which supplier/product combinations show repeated late deliveries?
- Which warehouses and product lines show the highest inventory movement/value estimates?
- Which AR/AP balances are overdue and concentrated by counterparty?
- How do DSO, DPO, DIO, and Cash Conversion Cycle estimates point to working-capital pressure?

## Core KPIs

- Revenue, quantity, average selling price, estimated COGS, gross profit, and gross margin
- Purchase quantity, average purchase price, lead time, and delivery delay
- Inventory quantity/value by product family, product line, and warehouse from movement/value records
- AR/AP outstanding, overdue balances, current/future balances, and aging buckets
- DSO, DPO, DIO, and Cash Conversion Cycle estimates

## Modeling Approach

Monthly chemical product demand is forecast for the next three months by `company` and `product_line` using a common horizon after the overall max sales month. Missing historical months are filled with zero before modeling. ARIMA is used when a company/product-line series has enough history; otherwise, the pipeline applies a trailing three-month average fallback so top product lines still have an analysis-ready planning estimate.

## Product Hierarchy

- `product_family` is the broader operating category derived from `item_category`, with `item_group` as fallback.
- `product_line` is the more granular parent product name from `parent_name`, with `product_family` as fallback.

## Assumptions

- Estimated COGS uses `quantity * moving_avg_cost`.
- Negative sales lines are retained as returns, credit-note, or reversal activity.
- AR/AP files are point-in-time aging snapshots, so outstanding balances are used as practical proxies for average AR/AP in DSO/DPO calculations.
- AR/AP aging buckets are standardized from `days_overdue`; `Current` contains due-today or future balances, and overdue buckets start at `1-30`.
- AR/AP document and counterparty counts include only records with `outstanding > 0`; zero-balance records may remain in source-level checks.
- The inventory file is an inventory movement/value export, not a clean audited month-end inventory snapshot.
- Inventory movement value uses `on_hand_qty * map_cost`; DIO is an approximate indicator based on available inventory movement/value records, not an audited inventory-days measure.
- Supplier lead time and delivery delay metrics are calculated only where actual delivery dates are available.
- Data-quality warnings should be reviewed before using the workbook for operational decisions.

## Confidentiality

The public repository excludes proprietary raw SAP exports. Public charts and examples use synthetic sample data from `data/sample/`; private exports belong in the ignored `data/raw/` folder.
