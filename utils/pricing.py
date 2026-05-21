from __future__ import annotations

import pandas as pd


def compute_costs(
    mats: pd.DataFrame,
    procs: pd.DataFrame,
    bom: pd.DataFrame,
    num_units: int = 1,
    overhead_base: str = "process",
    energy_rate_eur_kwh: float = 0.20,
) -> pd.DataFrame:
    """Compute full cost breakdown per BOM line.

    Parameters
    ----------
    num_units:
        Production run size; setup_h is amortised across this many units.
    overhead_base:
        "process"  — overhead on process cost only (marine industry default).
        "material" — overhead on material + process (legacy behaviour).
    energy_rate_eur_kwh:
        Electricity rate in €/kWh. Applied to energy_kw from Processes sheet.
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

    # ── Optional columns with safe defaults ──────────────────────────────────
    def _col(name: str, default) -> pd.Series:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(default)
        return pd.Series(default, index=df.index, dtype=float)

    setup_h      = _col("setup_h", 0.0)
    yield_factor = _col("yield_factor", 1.0).clip(lower=0.05)

    # New process-level cost columns
    tooling_consumable_eur_h = _col("tooling_consumable_eur_h", 0.0)
    rework_pct_col           = _col("rework_pct", 0.0)
    energy_kw                = _col("energy_kw", 0.0)
    subcontract_markup_pct   = _col("subcontract_markup_pct", 0.0)

    # MOQ excess cost (material-level, aggregated by material_id)
    moq_kg = _col("moq_kg", 0.0)

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

    # ── Quantity multiplier by cost type ─────────────────────────────────────
    qty_mult = qty.copy().astype(float)
    qty_mult[cost_type == "NRE"]     = 1.0         # one-off; not per unit
    qty_mult[cost_type == "TOOLING"] = qty / n      # amortised over run

    # Effective runtime = run time + setup amortised across production run
    effective_h = df["runtime_h"] + setup_h / n

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_bought       = make_buy == "B"
    has_subcontract = subcontract_price.notna() & (subcontract_price > 0)
    is_manufactured = ~is_bought & ~has_subcontract

    # ── Material cost: purchase quantity adjusted by yield factor ─────────────
    df["material_cost"] = qty_mult * (df["mass_kg"] / yield_factor) * df["price_eur_per_kg"]

    # ── MOQ excess cost ───────────────────────────────────────────────────────
    # When BOM quantity × mass_kg < moq_kg, buyer must purchase the MOQ minimum.
    # Record the excess cost as an additional material cost column (not in base_cost
    # by default — shown as a separate advisory column).
    purchased_kg  = qty_mult * (df["mass_kg"] / yield_factor)
    moq_excess_kg = (moq_kg - purchased_kg).clip(lower=0)
    df["moq_excess_cost"] = moq_excess_kg * df["price_eur_per_kg"]

    # ── Process cost ──────────────────────────────────────────────────────────
    proc_internal   = qty_mult * effective_h * (df["machine_rate_eur_h"] + df["labor_rate_eur_h"])
    df["process_cost"] = proc_internal.where(is_manufactured, other=0.0)

    # Subcontracted lines: price + markup
    subc_with_markup = qty_mult * subcontract_price * (1 + subcontract_markup_pct)
    df.loc[has_subcontract, "process_cost"] = subc_with_markup[has_subcontract]

    # Machine / labour split for reporting
    df["machine_cost"] = (qty_mult * effective_h * df["machine_rate_eur_h"]).where(
        is_manufactured, other=0.0
    )
    df["labour_cost"] = (qty_mult * effective_h * df["labor_rate_eur_h"]).where(
        is_manufactured, other=0.0
    )

    # ── Tooling consumables (cutting tools, grinding wheels, inserts) ──────────
    df["tooling_cost"] = (qty_mult * effective_h * tooling_consumable_eur_h).where(
        is_manufactured, other=0.0
    )

    # ── Energy cost ───────────────────────────────────────────────────────────
    df["energy_cost"] = (qty_mult * effective_h * energy_kw * energy_rate_eur_kwh).where(
        is_manufactured, other=0.0
    )

    # ── Rework provision ──────────────────────────────────────────────────────
    df["rework_cost"] = (df["process_cost"] * rework_pct_col).where(
        is_manufactured, other=0.0
    )

    # ── Overhead ──────────────────────────────────────────────────────────────
    # Marine standard: overhead on all process-related costs.
    # Bought-out items get a small handling charge (2%) instead.
    process_total = df["process_cost"] + df["tooling_cost"] + df["energy_cost"] + df["rework_cost"]

    if overhead_base == "process":
        df["overhead"] = process_total * df["overhead_pct"]
        df.loc[is_bought, "overhead"] = df.loc[is_bought, "material_cost"] * 0.02
    else:
        df["overhead"] = (df["material_cost"] + process_total) * df["overhead_pct"]

    df["base_cost"]  = df["material_cost"] + process_total + df["overhead"]
    df["margin"]     = df["base_cost"] * df["margin_pct"]
    df["total_cost"] = df["base_cost"] + df["margin"]
    return df
