"""Generate anonymized/synthetic sample workbooks with the raw SAP schemas."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from .config import RAW_DATASETS, SAMPLE_DATA_DIR, ensure_directories


RNG = np.random.default_rng(42)
COMPANIES = ["Matapel Chemicals Sample", "Matapel Tradindo Sample"]
PRODUCT_LINES = [
    ("PIG-001", "Organic Pigments", "Pigments", "Colorants"),
    ("PIG-002", "Inorganic Pigments", "Pigments", "Colorants"),
    ("RES-001", "Industrial Resins", "Resins", "Binders"),
    ("SOL-001", "Solvents", "Solvents", "Solvents"),
    ("ADD-001", "Additives", "Additives", "Specialty Chemicals"),
]
WAREHOUSES = ["Jakarta WH", "Surabaya WH", "Bandung WH"]
CUSTOMERS = [f"Customer {idx:03d}" for idx in range(1, 31)]
SUPPLIERS = [f"Supplier {idx:03d}" for idx in range(1, 16)]
EXCHANGE_RATE = 15_500


def excel_serial(date_value: pd.Timestamp | datetime) -> int:
    """Convert a timestamp to an Excel serial date."""

    timestamp = pd.Timestamp(date_value)
    return int((timestamp - pd.Timestamp("1899-12-30")).days)


def maybe_serial(date_value: pd.Timestamp, probability: float = 0.35):
    """Return either a Timestamp or Excel serial to mimic messy exports."""

    return excel_serial(date_value) if RNG.random() < probability else date_value


def build_master_product() -> pd.DataFrame:
    """Create a synthetic MasterProduct export."""

    rows = []
    for company in COMPANIES:
        for parent_code, parent_name, item_group, item_category in PRODUCT_LINES:
            for idx in range(1, 5):
                avg_cost = RNG.uniform(18_000, 95_000)
                rows.append(
                    {
                        "Company": company,
                        "ItemGroup": item_group,
                        "ItemCategory": item_category,
                        "ParentCode": parent_code,
                        "ParentName": parent_name,
                        "ItemCode": f"{parent_code}-{idx:02d}",
                        "ItemName": f"{parent_name} Grade {idx}",
                        "InvntryUom": "KG",
                        "AvgCost": round(avg_cost, 2),
                    }
                )
    return pd.DataFrame(rows)


def build_sales(master_product: pd.DataFrame) -> pd.DataFrame:
    """Create a synthetic SalesHist export."""

    months = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    rows = []
    for _, product in master_product.iterrows():
        base_demand = RNG.uniform(200, 1400)
        margin = RNG.uniform(1.12, 1.45)
        for month in months:
            if RNG.random() < 0.15:
                continue
            quantity = max(1, RNG.normal(base_demand, base_demand * 0.25))
            cost = float(product["AvgCost"]) * RNG.uniform(0.95, 1.08)
            price_idr = cost * margin
            inv_date = month + pd.Timedelta(days=int(RNG.integers(0, 26)))
            rows.append(
                {
                    "Company": product["Company"],
                    "InvDate": maybe_serial(inv_date),
                    "CustName": RNG.choice(CUSTOMERS),
                    "ItemGroup": product["ItemGroup"],
                    "ItemCategory": product["ItemCategory"],
                    "ParentCode": product["ParentCode"],
                    "ParentName": product["ParentName"],
                    "ItemCode": product["ItemCode"],
                    "ItemName": product["ItemName"],
                    "Quantity": round(quantity, 2),
                    "PriceUSD": round(price_idr / EXCHANGE_RATE, 4),
                    "TotalUSD": round(quantity * price_idr / EXCHANGE_RATE, 2),
                    "PriceIDR": round(price_idr, 2),
                    "TotalIDR": round(quantity * price_idr, 2),
                    "MovingAvgCost": round(cost, 2),
                }
            )
    return pd.DataFrame(rows)


def build_purchases(master_product: pd.DataFrame) -> pd.DataFrame:
    """Create a synthetic PurchHist export."""

    months = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    rows = []
    po_number = 100000
    for _, product in master_product.iterrows():
        for month in months[::2]:
            if RNG.random() < 0.25:
                continue
            po_number += 1
            doc_date = month + pd.Timedelta(days=int(RNG.integers(0, 12)))
            expected = doc_date + pd.Timedelta(days=int(RNG.integers(14, 35)))
            actual = expected + pd.Timedelta(days=int(RNG.normal(2, 6)))
            quantity = max(100, RNG.normal(2500, 800))
            doc_price = float(product["AvgCost"]) * RNG.uniform(0.82, 0.98) / EXCHANGE_RATE
            rows.append(
                {
                    "Company": product["Company"],
                    "PONumber": po_number,
                    "DocDate": maybe_serial(doc_date),
                    "ExpectedDelivDate": maybe_serial(expected),
                    "ActualDelivDate": maybe_serial(actual, probability=0.5),
                    "CardName": RNG.choice(SUPPLIERS),
                    "ItmsGrpNam": product["ItemGroup"],
                    "ItemCategory": product["ItemCategory"],
                    "ParentCode": product["ParentCode"],
                    "ParentName": product["ParentName"],
                    "ItemCode": product["ItemCode"],
                    "ItemName": product["ItemName"],
                    "Quantity": round(quantity, 2),
                    "DocCurrency": "USD",
                    "DocPrice": round(doc_price, 4),
                    "DocRate": EXCHANGE_RATE,
                    "ExcRate": EXCHANGE_RATE,
                    "PriceUSD": round(doc_price, 4),
                }
            )
    return pd.DataFrame(rows)


def build_inventory(master_product: pd.DataFrame) -> pd.DataFrame:
    """Create a synthetic Inventory export."""

    months = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    rows = []
    for _, product in master_product.iterrows():
        balance = RNG.uniform(500, 6000)
        for month in months:
            balance = max(-50, balance + RNG.normal(0, 700))
            warehouse = RNG.choice(WAREHOUSES)
            map_cost = float(product["AvgCost"]) * RNG.uniform(0.96, 1.06)
            rows.append(
                {
                    "Company": product["Company"],
                    "MovementDate": maybe_serial(month + pd.offsets.MonthEnd(0)),
                    "ItemGroup": product["ItemGroup"],
                    "ItemCategory": product["ItemCategory"],
                    "ParentCode": product["ParentCode"],
                    "ParentName": product["ParentName"],
                    "ItemCode": product["ItemCode"],
                    "ItemName": product["ItemName"],
                    "Warehouse": warehouse,
                    "OnHandQty": round(balance, 2),
                    "MAPCost": round(map_cost, 2),
                    "TransValue": round(balance * map_cost, 2),
                }
            )
    return pd.DataFrame(rows)


def build_aging(kind: str) -> pd.DataFrame:
    """Create a synthetic AR or AP aging detail export."""

    counterparties = CUSTOMERS if kind == "ar" else SUPPLIERS
    rows = []
    for idx in range(1, 180 if kind == "ar" else 80):
        inv_date = pd.Timestamp("2025-09-01") + pd.Timedelta(days=int(RNG.integers(0, 150)))
        terms = int(RNG.choice([14, 30, 45, 60]))
        due_date = inv_date + pd.Timedelta(days=terms)
        as_of = pd.Timestamp("2026-02-28")
        days_overdue = int((as_of - due_date).days)
        doc_total = float(RNG.uniform(5_000_000, 180_000_000))
        paid_to_date = doc_total * float(RNG.uniform(0, 0.8))
        outstanding = doc_total - paid_to_date
        if days_overdue <= 0:
            bucket = "Current"
        elif days_overdue <= 30:
            bucket = "1-30"
        elif days_overdue <= 60:
            bucket = "31-60"
        elif days_overdue <= 90:
            bucket = "61-90"
        else:
            bucket = "90+"
        rows.append(
            {
                "Company": RNG.choice(COMPANIES),
                "CardName": RNG.choice(counterparties),
                "InvNumber": f"{'AR' if kind == 'ar' else 'AP'}-{idx:05d}",
                "InvDate": maybe_serial(inv_date),
                "InvDueDate": maybe_serial(due_date),
                "PaymentDate.1": maybe_serial(inv_date + pd.Timedelta(days=int(RNG.integers(1, max(terms, 2))))),
                "PaymentDate.2": np.nan,
                "PymntGroup": f"Net {terms}",
                "ExtraDays": max(0, days_overdue),
                "DaysOverdue": days_overdue,
                "AgingBucket": bucket,
                "DocTotal": round(doc_total, 2),
                "PaidToDate": round(paid_to_date, 2),
                "Oustanding": round(outstanding, 2),
            }
        )
    return pd.DataFrame(rows)


def write_workbook(df: pd.DataFrame, file_name: str, sheet_name: str) -> None:
    """Write one raw-schema workbook to data/sample."""

    path = SAMPLE_DATA_DIR / file_name
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)


def generate_sample_data() -> dict[str, int]:
    """Generate all sample Excel workbooks and return row counts."""

    ensure_directories()
    master = build_master_product()
    tables = {
        "products": master,
        "sales": build_sales(master),
        "purchases": build_purchases(master),
        "inventory": build_inventory(master),
        "ar": build_aging("ar"),
        "ap": build_aging("ap"),
    }
    for key, df in tables.items():
        config = RAW_DATASETS[key]
        write_workbook(df, config.file_name, config.sheet_name)
    return {key: len(df) for key, df in tables.items()}


def main() -> int:
    """CLI entry point."""

    counts = generate_sample_data()
    print("Synthetic sample workbooks created in data/sample/.")
    for key, count in counts.items():
        print(f"{key}: {count:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
