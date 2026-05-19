from __future__ import annotations

import pandas as pd


def compute_costs(
    mats: pd.DataFrame,
    procs: pd.DataFrame,
    bom: pd.DataFrame,
    num_units: int = 1,
    overhead_base: str = "process",
) -> pd.DataFrame:
    """Compute full cost breakdown per BOM line.

    Parameters
    ----------
    num_units:
        Production run size; setup_h is amortised across this many units.
    overhead_base:
        "process"  — overhead on process cost only (marine industry default).
        "material" — overhead on material + process (legacy behaviour).
    """
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
    n   = max(int(num_units), 1)

    # Fill NaN from unmatched merges — service lines and unmatched routes get 0
    for _col in ["mass_kg", "price_eur_per_kg",
                 "machine_rate_eur_h", "labor_rate_eur_h",
                 "overhead_pct", "margin_pct"]:
        if _col in df.columns:
            df[_col] = pd.to_numeric(df[_col], errors="coerce").fillna(0)

    # ── Optional BOM columns with safe defaults ───────────────────────────────
    def _col(name: str, default) -> pd.Series:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(default)
        return pd.Series(default, index=df.index, dtype=float)

    setup_h      = _col("setup_h", 0.0)
    yield_factor = _col("yield_factor", 1.0).clip(lower=0.05)

    make_buy = (
        df["make_buy"].fillna("M").str.upper()
        if "make_buy" in df.columns
        else pd.Series("M", index=df.index)
    )
    cost_type = (
        df["cost_type"].fillna("UNIT").str.upper()
        if "cost_type" in df.columns
        else pd.Series("UNIT", index=df.index)
    )
    subcontract_price = (
        pd.to_numeric(df["subcontract_price_eur"], errors="coerce")
        if "subcontract_price_eur" in df.columns
        else pd.Series(float("nan"), index=df.index)
    )

    # ── Quantity multiplier by cost type ──────────────────────────────────────
    qty_mult = qty.copy().astype(float)
    qty_mult[cost_type == "NRE"]     = 1.0         # one-off; not per unit
    qty_mult[cost_type == "TOOLING"] = qty / n      # amortised over run

    # Effective runtime = run time + setup amortised across production run
    effective_h = df["runtime_h"] + setup_h / n

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_bought       = make_buy == "B"
    has_subcontract = subcontract_price.notna() & (subcontract_price > 0)

    # ── Material cost: purchase quantity adjusted by yield factor ─────────────
    df["material_cost"] = qty_mult * (df["mass_kg"] / yield_factor) * df["price_eur_per_kg"]

    # ── Process cost ──────────────────────────────────────────────────────────
    proc_internal   = qty_mult * effective_h * (df["machine_rate_eur_h"] + df["labor_rate_eur_h"])
    df["process_cost"] = proc_internal.where(~is_bought & ~has_subcontract, other=0.0)
    df.loc[has_subcontract, "process_cost"] = (
        qty_mult[has_subcontract] * subcontract_price[has_subcontract]
    )

    # Machine / labour split for reporting
    df["machine_cost"] = (qty_mult * effective_h * df["machine_rate_eur_h"]).where(
        ~is_bought & ~has_subcontract, other=0.0
    )
    df["labour_cost"] = (qty_mult * effective_h * df["labor_rate_eur_h"]).where(
        ~is_bought & ~has_subcontract, other=0.0
    )

    # ── Overhead ──────────────────────────────────────────────────────────────
    # Marine standard: overhead on process cost only (material is a direct passthrough).
    # Bought-out items get a small handling charge (2%) instead.
    if overhead_base == "process":
        df["overhead"] = df["process_cost"] * df["overhead_pct"]
        df.loc[is_bought, "overhead"] = df.loc[is_bought, "material_cost"] * 0.02
    else:
        df["overhead"] = (df["material_cost"] + df["process_cost"]) * df["overhead_pct"]

    df["base_cost"]  = df["material_cost"] + df["process_cost"] + df["overhead"]
    df["margin"]     = df["base_cost"] * df["margin_pct"]
    df["total_cost"] = df["base_cost"] + df["margin"]
    return df
