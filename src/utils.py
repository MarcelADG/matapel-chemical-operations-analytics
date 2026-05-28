"""Reusable utilities for cleaning SAP-style exports."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


AGING_BUCKET_ORDER = ["Current", "1-30", "31-60", "61-90", "90+"]


def to_snake_case(value: str) -> str:
    """Convert a source column name into a stable snake_case field name."""

    text = str(value).strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a dataframe with normalized column names."""

    out = df.copy()
    out.columns = [to_snake_case(col) for col in out.columns]
    out = out.rename(
        columns={
            "avgcost": "avg_cost",
            "mapcost": "map_cost",
            "oustanding": "outstanding",
            "ponumber": "po_number",
        }
    )
    return out


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse Excel serial dates, datetime values, and date strings safely.

    SAP/Excel exports can mix true Excel dates, serial numbers, blanks, and
    strings in the same column. Numeric values in a plausible Excel serial date
    range are interpreted using Excel's 1899-12-30 origin.
    """

    parsed = pd.to_datetime(series, errors="coerce")
    numeric = pd.to_numeric(series, errors="coerce")
    serial_mask = numeric.notna() & numeric.between(1, 80000)
    serial_dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if serial_mask.any():
        serial_dates.loc[serial_mask] = pd.to_datetime(
            numeric.loc[serial_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        ).to_numpy()
    parsed = parsed.mask(serial_mask, serial_dates)
    return parsed


def to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a potentially messy numeric field to float."""

    cleaned = (
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def strip_text_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Trim whitespace and normalize empty strings for text dimensions."""

    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].astype("string").str.strip()
            out[col] = out[col].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return out


def add_product_line(df: pd.DataFrame) -> pd.DataFrame:
    """Create product family and product line dimensions.

    product_family is the broader category derived from item_category or
    item_group. product_line is the more granular parent_name used for item-
    level sales and demand views, with product_family as the fallback.
    """

    out = df.copy()
    parent = out.get("parent_name", pd.Series(pd.NA, index=out.index)).astype("string").str.strip()
    category = out.get("item_category", pd.Series(pd.NA, index=out.index)).astype("string").str.strip()
    item_group = out.get("item_group", pd.Series(pd.NA, index=out.index)).astype("string").str.strip()
    out["product_family"] = category.replace("", pd.NA).fillna(item_group).fillna("Unknown")
    out["product_line"] = parent.replace("", pd.NA).fillna(out["product_family"]).fillna("Unknown")
    return out


def add_month(df: pd.DataFrame, date_column: str, month_column: str = "month") -> pd.DataFrame:
    """Add a first-of-month timestamp derived from a date column."""

    out = df.copy()
    if date_column in out.columns:
        out[month_column] = out[date_column].dt.to_period("M").dt.to_timestamp()
    else:
        out[month_column] = pd.NaT
    return out


def safe_divide(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series | float:
    """Divide while returning NaN where the denominator is zero or missing."""

    if isinstance(denominator, pd.Series):
        safe_denominator = denominator.replace(0, np.nan)
    else:
        safe_denominator = np.nan if denominator == 0 else denominator
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / safe_denominator
    if isinstance(result, pd.Series):
        return result.replace([np.inf, -np.inf], np.nan)
    if pd.isna(result) or np.isinf(result):
        return np.nan
    return result


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Save a dataframe to CSV with parent directory creation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def latest_month(series: pd.Series) -> pd.Timestamp | pd.NaT:
    """Return the latest non-null month from a datetime-like series."""

    valid = series.dropna()
    if valid.empty:
        return pd.NaT
    return valid.max()


def normalize_aging_bucket(value: object) -> str:
    """Normalize common AR/AP aging bucket labels to the reporting order."""

    text = str(value).strip() if pd.notna(value) else "Unknown"
    normalized = text.lower().replace(" ", "").replace("days", "")
    aliases = {
        "current": "Current",
        "notdue": "Current",
        "future": "Current",
        "0": "Current",
        "0-0": "Current",
        "1-30": "1-30",
        "1to30": "1-30",
        "0-30": "1-30",
        "31-60": "31-60",
        "31to60": "31-60",
        "61-90": "61-90",
        "61to90": "61-90",
        "90+": "90+",
        ">90": "90+",
        "91+": "90+",
        "91plus": "90+",
        "over90": "90+",
    }
    return aliases.get(normalized, text)


def aging_bucket_from_days(days_overdue: object, fallback_bucket: object = None) -> str:
    """Classify AR/AP balances into standard aging buckets from days overdue."""

    if pd.notna(days_overdue):
        days = float(days_overdue)
        if days <= 0:
            return "Current"
        if days <= 30:
            return "1-30"
        if days <= 60:
            return "31-60"
        if days <= 90:
            return "61-90"
        return "90+"
    return normalize_aging_bucket(fallback_bucket)


def add_aging_bucket_order(df: pd.DataFrame, bucket_col: str = "aging_bucket") -> pd.DataFrame:
    """Add normalized aging bucket labels and sort keys."""

    out = df.copy()
    out[bucket_col] = out[bucket_col].map(normalize_aging_bucket)
    order_map = {bucket: index for index, bucket in enumerate(AGING_BUCKET_ORDER)}
    out["aging_bucket_order"] = out[bucket_col].map(order_map).fillna(len(AGING_BUCKET_ORDER)).astype(int)
    return out
