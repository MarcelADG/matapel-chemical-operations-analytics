"""Load raw SAP-style Excel exports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RAW_DATASETS, RAW_DATA_DIR


def resolve_input_path(data_dir: Path, file_name: str) -> Path:
    """Resolve an input workbook path and raise a clear error if it is missing."""

    path = data_dir / file_name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required input file: {path}. "
            "Place the SAP export in data/raw/ or run with --sample after generating sample data."
        )
    return path


def load_excel_dataset(data_dir: Path, dataset_key: str) -> pd.DataFrame:
    """Load one configured Excel workbook and sheet."""

    dataset = RAW_DATASETS[dataset_key]
    path = resolve_input_path(data_dir, dataset.file_name)
    try:
        return pd.read_excel(path, sheet_name=dataset.sheet_name)
    except ValueError as exc:
        raise ValueError(
            f"Workbook {path} does not contain expected sheet '{dataset.sheet_name}'."
        ) from exc


def load_all_raw_data(data_dir: Path = RAW_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load all required raw datasets from a directory."""

    return {key: load_excel_dataset(data_dir, key) for key in RAW_DATASETS}

