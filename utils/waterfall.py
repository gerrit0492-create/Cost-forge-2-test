"""
Full cost waterfall builder.
Aggregates all cost modules into a single P&L-style cost build-up.
"""
from __future__ import annotations

import pandas as pd


def build_waterfall(
    *,
    material_cost: float = 0.0,
    inbound_freight: float = 0.0,
    duties: float = 0.0,
    process_cost: float = 0.0,
    overhead: float = 0.0,
    nre_per_run: float = 0.0,
    outbound_freight: float = 0.0,
    escalation_delta: float = 0.0,
    contingency: float = 0.0,
    margin_pct: float = 0.0,
    num_units: int = 1,
) -> pd.DataFrame:
    """
    Build a waterfall table from pre-computed cost component scalars.

    Parameters
    ----------
    material_cost, inbound_freight, ...: float
        Cost values in EUR.
    margin_pct:
        Margin as a fraction (e.g. 0.15 = 15%). Applied to the base cost.
    num_units:
        Number of units in the run (for display only).

    Returns
    -------
    DataFrame with columns: step, amount_eur, cumulative_eur, pct_of_sell
    """
    n = max(num_units, 1)

    steps = [
        ("1. Material (purchase)",     material_cost),
        ("2. Inbound freight & pkg",   inbound_freight),
        ("3. Import duties",           duties),
        ("4. Machining & labour",      process_cost),
        ("5. Overhead",                overhead),
        ("6. NRE (run)",               nre_per_run),
        ("7. Outbound shipping",       outbound_freight),
        ("8. Escalation adjustment",   escalation_delta),
        ("9. Contingency",             contingency),
    ]

    base_cost = sum(v for _, v in steps)
    margin    = base_cost * margin_pct
    sell      = base_cost + margin

    steps += [
        ("── Base cost",  base_cost),
        ("10. Margin",    margin),
        ("══ Sell price", sell),
    ]

    rows = []
    cumulative = 0.0
    for step, amount in steps:
        if step.startswith("──") or step.startswith("══"):
            # Subtotal / total rows — cumulative is the amount itself
            cumulative = amount
        else:
            cumulative += amount
        rows.append({
            "Step":          step,
            "Amount €":      round(amount, 2),
            "Cumulative €":  round(cumulative, 2),
            "% of sell":     round(amount / sell * 100, 1) if sell else 0,
        })

    df = pd.DataFrame(rows)
    return df


def waterfall_per_unit(
    waterfall_total: pd.DataFrame,
    num_units: int,
) -> pd.DataFrame:
    """Divide a total waterfall by num_units to get a per-unit view."""
    n = max(num_units, 1)
    df = waterfall_total.copy()
    df["Amount €"]     = (df["Amount €"] / n).round(2)
    df["Cumulative €"] = (df["Cumulative €"] / n).round(2)
    return df


def pnl_summary(waterfall: pd.DataFrame, num_units: int = 1) -> pd.DataFrame:
    """
    Convert a waterfall into a P&L format:
    Revenue / Direct material / Direct process / Overhead / ... / Gross margin
    """
    n = max(num_units, 1)

    def _get(step_prefix: str) -> float:
        rows = waterfall[waterfall["Step"].str.startswith(step_prefix)]
        return float(rows["Amount €"].sum()) if not rows.empty else 0.0

    sell     = _get("══ Sell")
    mat      = _get("1.")
    in_fr    = _get("2.")
    duties   = _get("3.")
    proc     = _get("4.")
    oh       = _get("5.")
    nre      = _get("6.")
    ob_fr    = _get("7.")
    esc      = _get("8.")
    cont     = _get("9.")
    margin   = _get("10.")
    base     = sell - margin

    cogs = mat + in_fr + duties + proc + oh + nre + ob_fr + esc + cont
    gm   = sell - cogs

    rows = [
        ("Revenue (sell price)",           sell,     sell,    ""),
        ("  Direct material (purchased)",  -mat,     sell-mat, ""),
        ("  Inbound freight & pkg",        -in_fr,   sell-mat-in_fr, ""),
        ("  Import duties",                -duties,  sell-mat-in_fr-duties, ""),
        ("  Machining & labour",           -proc,    sell-mat-in_fr-duties-proc, ""),
        ("  Overhead",                     -oh,      sell-mat-in_fr-duties-proc-oh, ""),
        ("  NRE (run total)",              -nre,     sell-mat-in_fr-duties-proc-oh-nre, ""),
        ("  Outbound freight",             -ob_fr,   sell-mat-in_fr-duties-proc-oh-nre-ob_fr, ""),
        ("  Escalation adj.",              -esc,     "", ""),
        ("  Contingency",                  -cont,    "", ""),
        ("Gross margin",                   gm,       gm, f"{gm/sell*100:.1f}%" if sell else "—"),
        ("Margin (commercial)",            margin,   margin, f"{margin/sell*100:.1f}%" if sell else "—"),
    ]

    return pd.DataFrame(rows, columns=["Item", "€ (run)", "Running €", "Note"])
