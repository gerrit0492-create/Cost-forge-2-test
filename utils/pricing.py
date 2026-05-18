from __future__ import annotations

import pandas as pd


def compute_costs(mats: pd.DataFrame, procs: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    df = (
        bom.merge(mats, on="material_id", how="left")
           .merge(procs, left_on="process_route", right_on="process_id", how="left")
    )
    required = [
        "qty", "mass_kg", "price_eur_per_kg",
        "runtime_h", "machine_rate_eur_h", "labor_rate_eur_h",
        "overhead_pct", "margin_pct",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns after merge: {missing}")

    qty = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
    df["material_cost"] = qty * df["mass_kg"] * df["price_eur_per_kg"]
    df["process_cost"]  = qty * df["runtime_h"] * (df["machine_rate_eur_h"] + df["labor_rate_eur_h"])
    df["overhead"]      = (df["material_cost"] + df["process_cost"]) * df["overhead_pct"]
    df["base_cost"]     = df["material_cost"] + df["process_cost"] + df["overhead"]
    df["margin"]        = df["base_cost"] * df["margin_pct"]
    df["total_cost"]    = df["base_cost"] + df["margin"]
    return df
