"""Project configuration and path constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SAMPLE_DATA_DIR = DATA_DIR / "sample"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SAMPLE_OUTPUTS_DIR = OUTPUTS_DIR / "sample"
PRIVATE_OUTPUTS_DIR = OUTPUTS_DIR / "private"

DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_IMAGES_DIR = DOCS_DIR / "images"
REPORTS_DIR = PROJECT_ROOT / "reports"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SQL_DIR = PROJECT_ROOT / "sql"


@dataclass(frozen=True)
class RawDataset:
    """Metadata needed to load a SAP-style Excel export."""

    name: str
    file_name: str
    sheet_name: str


@dataclass(frozen=True)
class OutputPaths:
    """Mode-specific pipeline output locations."""

    root: Path
    processed: Path
    tables: Path
    charts: Path
    excel: Path
    workbook: Path


RAW_DATASETS: dict[str, RawDataset] = {
    "sales": RawDataset("sales", "RequestData_SalesHist.xlsx", "Sales"),
    "purchases": RawDataset("purchases", "RequestData_PurchHist.xlsx", "PurchOrder"),
    "inventory": RawDataset("inventory", "RequestData_Inventory.xlsx", "Inventory"),
    "products": RawDataset("products", "RequestData_MasterProduct.xlsx", "MasterProduct"),
    "ar": RawDataset("ar", "RequestData_ARAging.xlsx", "Recv-AgingDet"),
    "ap": RawDataset("ap", "RequestData_APAging.xlsx", "Payb-AgingDet"),
}


DATE_COLUMNS: dict[str, list[str]] = {
    "sales": ["inv_date"],
    "purchases": ["doc_date", "expected_deliv_date", "actual_deliv_date"],
    "inventory": ["movement_date"],
    "ar": ["inv_date", "inv_due_date", "payment_date_1", "payment_date_2"],
    "ap": ["inv_date", "inv_due_date", "payment_date_1", "payment_date_2"],
}


def output_paths(output_root: Path) -> OutputPaths:
    """Return the output folders for one sample or private pipeline run."""

    return OutputPaths(
        root=output_root,
        processed=output_root / "processed",
        tables=output_root / "tables",
        charts=output_root / "charts",
        excel=output_root / "excel",
        workbook=output_root / "excel" / "matapel_dashboard_tables.xlsx",
    )


def ensure_directories() -> None:
    """Create stable project directories.

    Mode-specific output folders are created by the pipeline at runtime so
    sample and private outputs stay physically separated.
    """

    for path in [
        RAW_DATA_DIR,
        SAMPLE_DATA_DIR,
        SAMPLE_OUTPUTS_DIR,
        DOCS_IMAGES_DIR,
        REPORTS_DIR,
        NOTEBOOKS_DIR,
        SQL_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
