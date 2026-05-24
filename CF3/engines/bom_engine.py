from __future__ import annotations

import pandas as pd

REQUIRED_BOM_COLUMNS = ["item", "description", "qty"]
OPTIONAL_BOM_COLUMNS = [
    "material_id",
    "material",
    "unit_price",
    "material_cost",
    "process",
    "setup_hours",
    "run_hours",
    "machine_rate",
    "labour_rate",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data.columns = [str(col).strip().lower().replace(" ", "_") for col in data.columns]
    return data


def validate_bom(df: pd.DataFrame) -> list[str]:
    data = normalize_columns(df)
    errors: list[str] = []

    for column in REQUIRED_BOM_COLUMNS:
        if column not in data.columns:
            errors.append(f"Missing required column: {column}")

    if "qty" in data.columns:
        invalid_qty = pd.to_numeric(data["qty"], errors="coerce").fillna(0) <= 0
        if invalid_qty.any():
            errors.append(f"Invalid quantity rows: {int(invalid_qty.sum())}")

    if "item" in data.columns:
        duplicates = data["item"].duplicated().sum()
        if duplicates:
            errors.append(f"Duplicate item rows: {int(duplicates)}")

    return errors


def prepare_bom(df: pd.DataFrame) -> pd.DataFrame:
    data = normalize_columns(df)

    for column in REQUIRED_BOM_COLUMNS + OPTIONAL_BOM_COLUMNS:
        if column not in data.columns:
            data[column] = 0 if column not in ["item", "description", "material_id", "material", "process"] else ""

    numeric_columns = [
        "qty",
        "unit_price",
        "material_cost",
        "setup_hours",
        "run_hours",
        "machine_rate",
        "labour_rate",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    if (data["material_cost"] == 0).all():
        data["material_cost"] = data["qty"] * data["unit_price"]

    return data
