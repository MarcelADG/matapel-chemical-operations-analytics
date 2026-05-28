"""Feature engineering and reporting table builders."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import add_aging_bucket_order, safe_divide


def build_monthly_product_sales(fact_sales: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sales to company, month, product family, and product line."""

    grouped = (
        fact_sales.dropna(subset=["month"])
        .groupby(["company", "month", "product_family", "product_line"], dropna=False)
        .agg(
            quantity_sold=("quantity", "sum"),
            revenue_usd=("total_usd", "sum"),
            revenue_idr=("total_idr", "sum"),
            cogs_idr=("cogs_idr", "sum"),
            gross_profit_idr=("gross_profit_idr", "sum"),
            invoice_count=("item_code", "size"),
        )
        .reset_index()
        .sort_values(["company", "month", "product_line"])
    )
    grouped["avg_selling_price_idr"] = safe_divide(grouped["revenue_idr"], grouped["quantity_sold"])
    grouped["gross_margin_pct"] = safe_divide(grouped["gross_profit_idr"], grouped["revenue_idr"])
    return grouped


def build_monthly_sales_summary(fact_sales: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sales to company-month trends."""

    grouped = (
        fact_sales.dropna(subset=["month"])
        .groupby(["company", "month"], dropna=False)
        .agg(
            quantity_sold=("quantity", "sum"),
            revenue_usd=("total_usd", "sum"),
            revenue_idr=("total_idr", "sum"),
            cogs_idr=("cogs_idr", "sum"),
            gross_profit_idr=("gross_profit_idr", "sum"),
            customer_count=("cust_name", "nunique"),
            product_line_count=("product_line", "nunique"),
            invoice_line_count=("item_code", "size"),
        )
        .reset_index()
        .sort_values(["company", "month"])
    )
    grouped["avg_selling_price_idr"] = safe_divide(grouped["revenue_idr"], grouped["quantity_sold"])
    grouped["gross_margin_pct"] = safe_divide(grouped["gross_profit_idr"], grouped["revenue_idr"])
    return grouped


def build_product_line_performance(fact_sales: pd.DataFrame) -> pd.DataFrame:
    """Rank product lines by revenue, quantity, and estimated gross profit."""

    grouped = (
        fact_sales.groupby(["company", "product_family", "product_line"], dropna=False)
        .agg(
            quantity_sold=("quantity", "sum"),
            revenue_usd=("total_usd", "sum"),
            revenue_idr=("total_idr", "sum"),
            cogs_idr=("cogs_idr", "sum"),
            gross_profit_idr=("gross_profit_idr", "sum"),
            customer_count=("cust_name", "nunique"),
            active_months=("month", "nunique"),
        )
        .reset_index()
    )
    grouped["avg_selling_price_idr"] = safe_divide(grouped["revenue_idr"], grouped["quantity_sold"])
    grouped["gross_margin_pct"] = safe_divide(grouped["gross_profit_idr"], grouped["revenue_idr"])
    grouped["revenue_rank"] = grouped.groupby("company")["revenue_idr"].rank(method="dense", ascending=False)
    grouped["quantity_rank"] = grouped.groupby("company")["quantity_sold"].rank(method="dense", ascending=False)
    return grouped.sort_values(["company", "revenue_rank", "product_line"]).reset_index(drop=True)


def build_customer_performance(fact_sales: pd.DataFrame) -> pd.DataFrame:
    """Summarize sales by customer."""

    return (
        fact_sales.groupby(["company", "cust_name"], dropna=False)
        .agg(
            revenue_idr=("total_idr", "sum"),
            revenue_usd=("total_usd", "sum"),
            quantity_sold=("quantity", "sum"),
            product_lines=("product_line", "nunique"),
            invoice_lines=("item_code", "size"),
        )
        .reset_index()
        .sort_values(["company", "revenue_idr"], ascending=[True, False])
    )


def build_purchase_summary(fact_purchases: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build purchase price, supplier, and delivery performance summaries."""

    supplier_product = (
        fact_purchases.groupby(["company", "card_name", "product_family", "product_line"], dropna=False)
        .agg(
            purchase_quantity=("quantity", "sum"),
            avg_purchase_price_usd=("price_usd", "mean"),
            po_lines=("item_code", "size"),
            delivery_metric_records=("has_actual_delivery_date", "sum"),
            avg_lead_time_days=("purchase_lead_time_days", "mean"),
            avg_delivery_delay_days=("delivery_delay_days", "mean"),
            late_delivery_count=("is_late_delivery", "sum"),
        )
        .reset_index()
        .sort_values(["company", "late_delivery_count", "purchase_quantity"], ascending=[True, False, False])
    )

    price_trend = (
        fact_purchases.dropna(subset=["month"])
        .groupby(["company", "month", "product_family", "product_line"], dropna=False)
        .agg(
            purchase_quantity=("quantity", "sum"),
            avg_purchase_price_usd=("price_usd", "mean"),
            po_lines=("item_code", "size"),
        )
        .reset_index()
        .sort_values(["company", "product_line", "month"])
    )

    late_delivery_categories = (
        fact_purchases[fact_purchases["is_late_delivery"]]
        .groupby(["company", "card_name", "product_family", "product_line"], dropna=False)
        .agg(
            late_delivery_count=("is_late_delivery", "sum"),
            avg_delay_days=("delivery_delay_days", "mean"),
            max_delay_days=("delivery_delay_days", "max"),
        )
        .reset_index()
        .sort_values(["company", "late_delivery_count", "avg_delay_days"], ascending=[True, False, False])
    )

    return {
        "purchase_supplier_product": supplier_product,
        "purchase_price_trend": price_trend,
        "late_delivery_categories": late_delivery_categories,
    }


def build_monthly_inventory_summary(fact_inventory: pd.DataFrame) -> pd.DataFrame:
    """Aggregate inventory by company, month, product line, and warehouse."""

    grouped = (
        fact_inventory.dropna(subset=["month"])
        .groupby(["company", "month", "product_family", "product_line", "warehouse"], dropna=False)
        .agg(
            on_hand_qty=("on_hand_qty", "sum"),
            inventory_value_idr=("inventory_value_idr", "sum"),
            avg_map_cost=("map_cost", "mean"),
            item_count=("item_code", "nunique"),
            negative_inventory_lines=("is_negative_inventory", "sum"),
            zero_inventory_lines=("is_zero_inventory", "sum"),
            negative_value_lines=("is_negative_value", "sum"),
        )
        .reset_index()
        .sort_values(["company", "month", "product_line", "warehouse"])
    )
    latest_month = grouped["month"].max()
    latest = grouped["month"].eq(latest_month)
    value_threshold = grouped.loc[latest, "inventory_value_idr"].quantile(0.8) if latest.any() else np.nan
    qty_threshold = grouped.loc[latest, "on_hand_qty"].quantile(0.2) if latest.any() else np.nan
    grouped["is_high_value_inventory"] = grouped["inventory_value_idr"] >= value_threshold if pd.notna(value_threshold) else False
    grouped["is_slow_moving_indicator"] = (
        latest
        & grouped["is_high_value_inventory"]
        & (grouped["on_hand_qty"] <= qty_threshold if pd.notna(qty_threshold) else False)
    )
    return grouped


def build_aging_summary(fact_aging: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Summarize AR or AP by aging bucket."""

    ordered = add_aging_bucket_order(fact_aging)
    positive_outstanding = ordered["outstanding"].fillna(0) > 0
    ordered["outstanding_document"] = ordered["inv_number"].where(positive_outstanding)
    ordered["outstanding_counterparty"] = ordered["card_name"].where(positive_outstanding)
    return (
        ordered.groupby(["company", "aging_bucket_order", "aging_bucket"], dropna=False)
        .agg(
            outstanding=("outstanding", "sum"),
            overdue_amount=("overdue_amount", "sum"),
            current_or_future_amount=("current_or_future_amount", "sum"),
            document_count=("outstanding_document", "nunique"),
            counterparty_count=("outstanding_counterparty", "nunique"),
            record_count=("inv_number", "size"),
        )
        .reset_index()
        .assign(table=table_name)
        .sort_values(["aging_bucket_order", "company"])
        .drop(columns=["aging_bucket_order"])
    )


def build_top_overdue(fact_aging: pd.DataFrame, counterparty_label: str) -> pd.DataFrame:
    """Rank customers or suppliers by positive overdue exposure."""

    overdue = fact_aging[fact_aging["overdue_amount"].fillna(0) > 0]
    return (
        overdue
        .groupby(["company", "card_name"], dropna=False)
        .agg(
            overdue_amount=("overdue_amount", "sum"),
            outstanding=("outstanding", "sum"),
            max_days_overdue=("days_overdue", "max"),
            overdue_documents=("inv_number", "nunique"),
        )
        .reset_index()
        .rename(columns={"card_name": counterparty_label})
        .sort_values(["company", "overdue_amount"], ascending=[True, False])
    )


def build_reporting_tables(cleaned: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build all derived reporting tables from cleaned facts."""

    sales = cleaned["fact_sales"]
    purchases = cleaned["fact_purchases"]
    inventory = cleaned["fact_inventory"]
    ar = cleaned["fact_ar"]
    ap = cleaned["fact_ap"]

    purchase_tables = build_purchase_summary(purchases)
    tables = {
        "monthly_product_sales": build_monthly_product_sales(sales),
        "monthly_sales_summary": build_monthly_sales_summary(sales),
        "product_line_performance": build_product_line_performance(sales),
        "customer_performance": build_customer_performance(sales),
        "monthly_inventory_summary": build_monthly_inventory_summary(inventory),
        "ar_aging_summary": build_aging_summary(ar, "AR"),
        "ap_aging_summary": build_aging_summary(ap, "AP"),
        "top_customers_overdue_ar": build_top_overdue(ar, "customer"),
        "top_suppliers_overdue_ap": build_top_overdue(ap, "supplier"),
    }
    tables.update(purchase_tables)
    return tables
