"""Cleaning logic for raw SAP exports."""

from __future__ import annotations

import pandas as pd

from .config import DATE_COLUMNS
from .utils import (
    add_month,
    add_product_line,
    aging_bucket_from_days,
    parse_mixed_dates,
    safe_divide,
    standardize_columns,
    strip_text_columns,
    to_numeric,
)


TEXT_FIELDS = [
    "company",
    "cust_name",
    "card_name",
    "item_group",
    "itms_grp_nam",
    "item_category",
    "parent_code",
    "parent_name",
    "item_code",
    "item_name",
    "warehouse",
    "doc_currency",
    "pymnt_group",
    "aging_bucket",
    "invntry_uom",
]


def _base_clean(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Apply shared column, text, and date cleanup."""

    out = standardize_columns(df)
    out = strip_text_columns(out, TEXT_FIELDS)
    for col in DATE_COLUMNS.get(table_name, []):
        if col in out.columns:
            out[col] = parse_mixed_dates(out[col])
    return out.drop_duplicates().reset_index(drop=True)


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Clean SalesHist into fact_sales."""

    out = _base_clean(df, "sales")
    for col in ["quantity", "price_usd", "total_usd", "price_idr", "total_idr", "moving_avg_cost"]:
        if col in out.columns:
            out[col] = to_numeric(out[col])
    out = add_product_line(out)
    out = add_month(out, "inv_date")
    out["cogs_idr"] = out["quantity"] * out["moving_avg_cost"]
    out["gross_profit_idr"] = out["total_idr"] - out["cogs_idr"]
    out["gross_margin_pct"] = safe_divide(out["gross_profit_idr"], out["total_idr"])
    return out


def clean_purchases(df: pd.DataFrame) -> pd.DataFrame:
    """Clean PurchHist into fact_purchases."""

    out = _base_clean(df, "purchases")
    for col in ["po_number", "quantity", "doc_price", "doc_rate", "exc_rate", "price_usd"]:
        if col in out.columns:
            out[col] = to_numeric(out[col])
    out = add_product_line(out)
    out = add_month(out, "doc_date")
    out["purchase_lead_time_days"] = (out["actual_deliv_date"] - out["doc_date"]).dt.days
    out["delivery_delay_days"] = (out["actual_deliv_date"] - out["expected_deliv_date"]).dt.days
    out["has_actual_delivery_date"] = out["actual_deliv_date"].notna()
    out["is_late_delivery"] = out["has_actual_delivery_date"] & out["delivery_delay_days"].gt(0)
    return out


def clean_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Clean Inventory into fact_inventory."""

    out = _base_clean(df, "inventory")
    for col in ["on_hand_qty", "map_cost", "trans_value"]:
        if col in out.columns:
            out[col] = to_numeric(out[col])
    out = add_product_line(out)
    out = add_month(out, "movement_date")
    out["inventory_value_idr"] = out["on_hand_qty"] * out["map_cost"]
    out["is_negative_inventory"] = out["on_hand_qty"] < 0
    out["is_zero_inventory"] = out["on_hand_qty"].fillna(0) == 0
    out["is_negative_value"] = out["inventory_value_idr"] < 0
    return out


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    """Clean MasterProduct into dim_product."""

    out = _base_clean(df, "products")
    for col in ["avg_cost"]:
        if col in out.columns:
            out[col] = to_numeric(out[col])
    out = add_product_line(out)
    key_cols = ["company", "item_code"]
    existing_keys = [col for col in key_cols if col in out.columns]
    if existing_keys:
        out = out.drop_duplicates(subset=existing_keys, keep="last")
    return out.reset_index(drop=True)


def clean_aging(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Clean AR/AP aging details into fact_ar or fact_ap."""

    out = _base_clean(df, table_name)
    for col in ["extra_days", "days_overdue", "doc_total", "paid_to_date", "outstanding"]:
        if col in out.columns:
            out[col] = to_numeric(out[col])
    if "aging_bucket" in out.columns:
        out["source_aging_bucket"] = out["aging_bucket"]
    else:
        out["source_aging_bucket"] = pd.NA
    out["aging_bucket"] = [
        aging_bucket_from_days(days, bucket)
        for days, bucket in zip(out["days_overdue"], out["source_aging_bucket"], strict=False)
    ]
    out["is_overdue"] = out["days_overdue"].fillna(0) > 0
    out["aging_status"] = out["is_overdue"].map({True: "Overdue", False: "Current/Future"})
    out["current_or_future_amount"] = out["outstanding"].where(~out["is_overdue"], 0)
    out["overdue_amount"] = out["outstanding"].where(out["is_overdue"], 0)
    out = add_month(out, "inv_date", "invoice_month")
    out = add_month(out, "inv_due_date", "due_month")
    return out


def clean_all(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean all raw inputs into analytics-ready tables."""

    return {
        "fact_sales": clean_sales(raw["sales"]),
        "fact_purchases": clean_purchases(raw["purchases"]),
        "fact_inventory": clean_inventory(raw["inventory"]),
        "fact_ar": clean_aging(raw["ar"], "ar"),
        "fact_ap": clean_aging(raw["ap"], "ap"),
        "dim_product": clean_products(raw["products"]),
    }
