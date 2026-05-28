"""Data quality checks for cleaned analytics tables."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _result(
    table: str,
    check_name: str,
    severity: str,
    records_checked: int,
    issue_count: int,
    details: str,
) -> dict[str, object]:
    """Return one validation result row."""

    status = "PASS" if issue_count == 0 else "WARN" if severity != "high" else "FAIL"
    issue_rate = issue_count / records_checked if records_checked else 0
    return {
        "table_name": table,
        "check_name": check_name,
        "severity": severity,
        "status": status,
        "records_checked": records_checked,
        "issue_count": int(issue_count),
        "issue_rate": issue_rate,
        "details": details,
    }


def _missing_checks(table: str, df: pd.DataFrame) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing:
            results.append(_result(table, f"missing_values:{col}", "medium", len(df), missing, f"{missing} missing values in {col}"))
    return results


def _duplicate_check(table: str, df: pd.DataFrame, keys: list[str]) -> dict[str, object]:
    existing = [col for col in keys if col in df.columns]
    if not existing:
        return _result(table, "duplicate_key_check", "low", len(df), 0, "No configured keys present.")
    duplicates = int(df.duplicated(subset=existing, keep=False).sum())
    return _result(table, "duplicate_key_check", "medium", len(df), duplicates, f"Duplicate rows on keys: {', '.join(existing)}")


def _invalid_date_checks(table: str, df: pd.DataFrame, date_cols: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for col in date_cols:
        if col in df.columns:
            invalid = int(df[col].isna().sum())
            results.append(_result(table, f"invalid_or_missing_date:{col}", "medium", len(df), invalid, f"Null dates after parsing in {col}"))
    return results


def _negative_checks(table: str, df: pd.DataFrame, cols: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for col in cols:
        if col in df.columns:
            issue_count = int((df[col] < 0).sum())
            results.append(_result(table, f"negative_values:{col}", "medium", len(df), issue_count, f"Negative values in {col}"))
    return results


def _approx_mismatch(actual: pd.Series, expected: pd.Series, rel_tol: float = 0.02, abs_tol: float = 1.0) -> pd.Series:
    """Return a boolean mask for values outside a practical tolerance."""

    actual = actual.astype(float)
    expected = expected.astype(float)
    tolerance = np.maximum(abs_tol, expected.abs() * rel_tol)
    comparable = actual.notna() & expected.notna()
    return comparable & ((actual - expected).abs() > tolerance)


def validate_sales(fact_sales: pd.DataFrame) -> list[dict[str, object]]:
    """Run sales-specific validations."""

    results = []
    usd_mismatch = _approx_mismatch(fact_sales["total_usd"], fact_sales["quantity"] * fact_sales["price_usd"], rel_tol=0.02, abs_tol=1.0)
    idr_mismatch = _approx_mismatch(fact_sales["total_idr"], fact_sales["quantity"] * fact_sales["price_idr"], rel_tol=0.02, abs_tol=1000.0)
    results.append(_result("fact_sales", "sales_total_usd_reconciliation", "medium", len(fact_sales), int(usd_mismatch.sum()), "total_usd should approximately equal quantity * price_usd"))
    results.append(_result("fact_sales", "sales_total_idr_reconciliation", "medium", len(fact_sales), int(idr_mismatch.sum()), "total_idr should approximately equal quantity * price_idr"))
    return results


def validate_aging(table: str, df: pd.DataFrame) -> list[dict[str, object]]:
    """Run AR/AP outstanding reconciliation checks."""

    mismatch = _approx_mismatch(df["outstanding"], df["doc_total"] - df["paid_to_date"], rel_tol=0.02, abs_tol=1000.0)
    return [_result(table, "outstanding_reconciliation", "medium", len(df), int(mismatch.sum()), "outstanding should approximately equal doc_total - paid_to_date")]


def validate_all(cleaned: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run the full validation suite and return a data quality report."""

    duplicate_keys = {
        "fact_sales": ["company", "inv_date", "cust_name", "item_code", "quantity", "total_idr"],
        "fact_purchases": ["company", "po_number", "item_code", "doc_date"],
        "fact_inventory": ["company", "movement_date", "item_code", "warehouse"],
        "fact_ar": ["company", "inv_number", "card_name"],
        "fact_ap": ["company", "inv_number", "card_name"],
        "dim_product": ["company", "item_code"],
    }
    date_columns = {
        "fact_sales": ["inv_date"],
        "fact_purchases": ["doc_date", "expected_deliv_date", "actual_deliv_date"],
        "fact_inventory": ["movement_date"],
        "fact_ar": ["inv_date", "inv_due_date"],
        "fact_ap": ["inv_date", "inv_due_date"],
    }
    negative_columns = {
        "fact_sales": ["quantity", "total_usd", "total_idr"],
        "fact_purchases": ["quantity", "price_usd"],
        "fact_inventory": ["on_hand_qty", "inventory_value_idr"],
        "fact_ar": ["doc_total", "paid_to_date", "outstanding"],
        "fact_ap": ["doc_total", "paid_to_date", "outstanding"],
    }

    results: list[dict[str, object]] = []
    for table, df in cleaned.items():
        results.extend(_missing_checks(table, df))
        results.append(_duplicate_check(table, df, duplicate_keys.get(table, [])))
        results.extend(_invalid_date_checks(table, df, date_columns.get(table, [])))
        results.extend(_negative_checks(table, df, negative_columns.get(table, [])))

    results.extend(validate_sales(cleaned["fact_sales"]))
    results.extend(validate_aging("fact_ar", cleaned["fact_ar"]))
    results.extend(validate_aging("fact_ap", cleaned["fact_ap"]))

    report = pd.DataFrame(results)
    if report.empty:
        report = pd.DataFrame(
            [_result("all_tables", "validation_suite", "low", 0, 0, "No validation checks were created.")]
        )
    return report.sort_values(["status", "severity", "table_name", "check_name"], ascending=[True, False, True, True]).reset_index(drop=True)
