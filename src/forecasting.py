"""Demand forecasting by company and product line."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def _future_months(last_month: pd.Timestamp, periods: int = 3) -> pd.DatetimeIndex:
    """Return the next N month-start dates."""

    return pd.date_range(last_month + pd.offsets.MonthBegin(1), periods=periods, freq="MS")


def _trailing_average_forecast(history: pd.Series, forecast_months: pd.DatetimeIndex, note: str) -> pd.DataFrame:
    """Fallback forecast using recent trailing average demand."""

    trailing = history.tail(3)
    average = max(0.0, float(trailing.mean())) if not trailing.empty else 0.0
    std = float(trailing.std(ddof=0)) if len(trailing) > 1 else 0.0
    lower = max(0.0, average - 1.96 * std)
    upper = average + 1.96 * std
    return pd.DataFrame(
        {
            "forecast_month": forecast_months,
            "forecast_quantity": average,
            "lower_bound": lower,
            "upper_bound": upper,
            "model_used": "trailing_3_month_average",
            "training_months": int(history.count()),
            "notes": note,
        }
    )


def _arima_forecast(history: pd.Series, forecast_months: pd.DatetimeIndex) -> pd.DataFrame:
    """Forecast with ARIMA when enough monthly history is available."""

    from statsmodels.tsa.arima.model import ARIMA

    model = ARIMA(history.astype(float), order=(1, 1, 1))
    fit = model.fit()
    result = fit.get_forecast(steps=len(forecast_months))
    predicted = result.predicted_mean
    conf = result.conf_int(alpha=0.2)
    lower_col, upper_col = conf.columns[0], conf.columns[1]
    return pd.DataFrame(
        {
            "forecast_month": forecast_months,
            "forecast_quantity": np.maximum(0, predicted.to_numpy()),
            "lower_bound": np.maximum(0, conf[lower_col].to_numpy()),
            "upper_bound": np.maximum(0, conf[upper_col].to_numpy()),
            "model_used": "ARIMA(1,1,1)",
            "training_months": int(history.count()),
            "notes": "ARIMA used because product line has sufficient monthly history. Missing historical months were filled with zero through the overall max sales month.",
        }
    )


def forecast_product_line(
    history: pd.Series,
    history_end_month: pd.Timestamp,
    periods: int = 3,
) -> pd.DataFrame:
    """Forecast one company/product-line series using a common history end month."""

    history = history.sort_index()
    history_end_month = pd.Timestamp(history_end_month).to_period("M").to_timestamp()
    full_index = pd.date_range(history.index.min(), history_end_month, freq="MS")
    history = history.reindex(full_index).fillna(0)
    forecast_months = _future_months(history_end_month, periods=periods)
    if history.count() < 6 or history.sum() <= 0:
        return _trailing_average_forecast(
            history,
            forecast_months,
            "Fallback used because fewer than 6 months of usable demand history were available. Missing historical months were filled with zero through the overall max sales month.",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _arima_forecast(history, forecast_months)
    except Exception as exc:  # pragma: no cover - intentionally robust portfolio fallback
        return _trailing_average_forecast(history, forecast_months, f"Fallback used because ARIMA could not fit cleanly: {exc.__class__.__name__}.")


def build_forecast_results(monthly_product_sales: pd.DataFrame, top_n: int = 5, periods: int = 3) -> pd.DataFrame:
    """Forecast demand for top product lines using one global forecast horizon."""

    columns = [
        "company",
        "product_line",
        "forecast_month",
        "forecast_quantity",
        "lower_bound",
        "upper_bound",
        "model_used",
        "training_months",
        "notes",
    ]

    if monthly_product_sales.empty:
        return pd.DataFrame(columns=columns)

    working = monthly_product_sales.copy()
    working["month"] = pd.to_datetime(working["month"], errors="coerce")
    working = working.dropna(subset=["month"])
    if working.empty:
        return pd.DataFrame(columns=columns)

    overall_max_month = working["month"].max().to_period("M").to_timestamp()
    ranking = (
        working.groupby(["company", "product_line"], dropna=False)
        .agg(revenue_idr=("revenue_idr", "sum"), quantity_sold=("quantity_sold", "sum"))
        .reset_index()
    )
    top_by_revenue = (
        ranking.sort_values(["company", "revenue_idr"], ascending=[True, False])
        .groupby("company", dropna=False)
        .head(top_n)[["company", "product_line"]]
    )
    top_by_quantity = (
        ranking.sort_values(["company", "quantity_sold"], ascending=[True, False])
        .groupby("company", dropna=False)
        .head(top_n)[["company", "product_line"]]
    )
    selected = pd.concat([top_by_revenue, top_by_quantity], ignore_index=True).drop_duplicates()
    selected_keys = {tuple(row) for row in selected[["company", "product_line"]].itertuples(index=False, name=None)}

    outputs = []
    for (company, product_line), subset in working.groupby(["company", "product_line"], dropna=False):
        if (company, product_line) not in selected_keys:
            continue
        history = subset.groupby("month")["quantity_sold"].sum().sort_index()
        forecast = forecast_product_line(history, history_end_month=overall_max_month, periods=periods)
        forecast.insert(0, "company", company)
        forecast.insert(0, "product_line", product_line)
        forecast = forecast[columns]
        outputs.append(forecast)

    if not outputs:
        return pd.DataFrame(columns=columns)
    return pd.concat(outputs, ignore_index=True).sort_values(["company", "product_line", "forecast_month"])
