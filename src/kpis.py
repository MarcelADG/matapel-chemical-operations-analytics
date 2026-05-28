"""Working capital KPI calculations."""

from __future__ import annotations

import pandas as pd

from .utils import safe_divide


def _period_days(fact_sales: pd.DataFrame) -> int:
    """Calculate the number of days represented by the sales history."""

    dates = fact_sales["inv_date"].dropna()
    if dates.empty:
        return 365
    return max(1, int((dates.max() - dates.min()).days) + 1)


def build_working_capital_kpis(
    fact_sales: pd.DataFrame,
    fact_inventory: pd.DataFrame,
    fact_ar: pd.DataFrame,
    fact_ap: pd.DataFrame,
) -> pd.DataFrame:
    """Estimate AR/AP/inventory working-capital metrics.

    The aging exports are point-in-time detail files, so outstanding AR/AP are
    used as a snapshot proxy for average balances. The inventory export is
    treated as movement/value detail rather than an audited month-end snapshot,
    so DIO is an approximate planning indicator.
    """

    days = _period_days(fact_sales)
    revenue_idr = fact_sales["total_idr"].sum()
    cogs_idr = fact_sales["cogs_idr"].sum()

    monthly_inventory = (
        fact_inventory.dropna(subset=["month"])
        .groupby("month", dropna=False)["inventory_value_idr"]
        .sum()
    )
    average_inventory_idr = monthly_inventory.mean() if not monthly_inventory.empty else 0

    total_ar_outstanding = fact_ar["outstanding"].sum()
    total_ap_outstanding = fact_ap["outstanding"].sum()
    overdue_ar = fact_ar.loc[fact_ar["is_overdue"], "outstanding"].sum()
    overdue_ap = fact_ap.loc[fact_ap["is_overdue"], "outstanding"].sum()
    current_or_future_ar = fact_ar["current_or_future_amount"].sum()
    current_or_future_ap = fact_ap["current_or_future_amount"].sum()

    dso = safe_divide(total_ar_outstanding, revenue_idr) * days
    dpo = safe_divide(total_ap_outstanding, cogs_idr) * days
    dio = safe_divide(average_inventory_idr, cogs_idr) * days
    ccc = dio + dso - dpo

    return pd.DataFrame(
        [
            {
                "period_start": fact_sales["inv_date"].min(),
                "period_end": fact_sales["inv_date"].max(),
                "period_days": days,
                "revenue_idr": revenue_idr,
                "cogs_idr": cogs_idr,
                "average_inventory_idr": average_inventory_idr,
                "total_ar_outstanding": total_ar_outstanding,
                "total_ap_outstanding": total_ap_outstanding,
                "overdue_ar": overdue_ar,
                "overdue_ap": overdue_ap,
                "current_or_future_ar": current_or_future_ar,
                "current_or_future_ap": current_or_future_ap,
                "dso_days": dso,
                "dpo_days": dpo,
                "dio_days": dio,
                "cash_conversion_cycle_days": ccc,
                "assumption": "AR/AP are aging snapshot balances; DIO is an approximate indicator from available inventory movement/value records; COGS is estimated from moving average cost.",
            }
        ]
    )


def executive_summary_table(working_capital_kpis: pd.DataFrame) -> pd.DataFrame:
    """Create a compact KPI table for the Excel Executive Summary sheet."""

    row = working_capital_kpis.iloc[0].to_dict()
    metrics = [
        ("Revenue IDR", row["revenue_idr"], "IDR"),
        ("Estimated COGS IDR", row["cogs_idr"], "IDR"),
        ("Total AR Outstanding", row["total_ar_outstanding"], "IDR"),
        ("Total AP Outstanding", row["total_ap_outstanding"], "IDR"),
        ("Overdue AR", row["overdue_ar"], "IDR"),
        ("Overdue AP", row["overdue_ap"], "IDR"),
        ("DSO Estimate", row["dso_days"], "Days"),
        ("DPO Estimate", row["dpo_days"], "Days"),
        ("DIO Estimate", row["dio_days"], "Days"),
        ("Cash Conversion Cycle", row["cash_conversion_cycle_days"], "Days"),
    ]
    return pd.DataFrame(metrics, columns=["metric", "value", "unit"])
