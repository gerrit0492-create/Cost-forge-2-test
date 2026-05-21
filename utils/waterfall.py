"""
Full cost waterfall builder.
Aggregates all cost modules into a single P&L-style cost build-up.
"""
from __future__ import annotations

import pandas as pd


def build_waterfall(
    *,
    material_cost: float = 0.0,
    moq_cost: float = 0.0,
    pattern_cost: float = 0.0,
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
    material_cost : float
        Raw material purchase cost (kg × €/kg or per-unit bought-out price).
    moq_cost : float
        Minimum-order-quantity excess — material bought but not consumed.
    pattern_cost : float
        Casting pattern / die / mould cost (amortised per unit).
    inbound_freight, duties : float
        Landed material cost elements.
    process_cost : float
        Machining, welding, assembly (machine + labour + tooling + energy + rework).
    overhead : float
        Factory overhead on process cost.
    nre_per_run, outbound_freight, escalation_delta, contingency : float
        Additional cost elements.
    margin_pct : float
        Commercial margin as a fraction (0.20 = 20%).
    num_units : int
        Production run size (for display only; does not scale costs).
    """
    steps = [
        ("1. Material (purchase)",    material_cost),
        ("2. MOQ excess",             moq_cost),
        ("3. Pattern / tooling NRE",  pattern_cost),
        ("4. Inbound freight & pkg",  inbound_freight),
        ("5. Import duties",          duties),
        ("6. Machining & labour",     process_cost),
        ("7. Overhead",               overhead),
        ("8. NRE (run)",              nre_per_run),
        ("9. Outbound shipping",      outbound_freight),
        ("10. Escalation adjustment", escalation_delta),
        ("11. Contingency",           contingency),
    ]

    base_cost = sum(v for _, v in steps)
    margin    = base_cost * margin_pct
    sell      = base_cost + margin

    steps += [
        ("── Base cost",  base_cost),
        ("12. Margin",    margin),
        ("══ Sell price", sell),
    ]

    rows = []
    cumulative = 0.0
    for step, amount in steps:
        if step.startswith("──") or step.startswith("══"):
            cumulative = amount
        else:
            cumulative += amount
        rows.append({
            "Step":         step,
            "Amount €":     round(amount, 2),
            "Cumulative €": round(cumulative, 2),
            "% of sell":    round(amount / sell * 100, 1) if sell else 0,
        })

    return pd.DataFrame(rows)


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
    Revenue / Direct material / MOQ excess / Pattern NRE / Process / Overhead / ... / Gross margin
    """
    def _get(step_prefix: str) -> float:
        rows = waterfall[waterfall["Step"].str.startswith(step_prefix)]
        return float(rows["Amount €"].sum()) if not rows.empty else 0.0

    sell    = _get("══ Sell")
    mat     = _get("1.")
    moq     = _get("2.")
    pattern = _get("3.")
    in_fr   = _get("4.")
    duties  = _get("5.")
    proc    = _get("6.")
    oh      = _get("7.")
    nre     = _get("8.")
    ob_fr   = _get("9.")
    esc     = _get("10.")
    cont    = _get("11.")
    margin  = _get("12.")

    cogs = mat + moq + pattern + in_fr + duties + proc + oh + nre + ob_fr + esc + cont
    gm   = sell - cogs

    rows = [
        ("Revenue (sell price)",           sell,  sell,  ""),
        ("  Direct material (purchased)", -mat,   sell-mat,  ""),
        ("  MOQ excess",                  -moq,   sell-mat-moq, "min-order waste"),
        ("  Pattern / tooling NRE",       -pattern, sell-mat-moq-pattern, "amortised casting cost"),
        ("  Inbound freight & pkg",       -in_fr, "", ""),
        ("  Import duties",               -duties, "", ""),
        ("  Machining & labour",          -proc,  "", ""),
        ("  Overhead",                    -oh,    "", ""),
        ("  NRE (run total)",             -nre,   "", ""),
        ("  Outbound freight",            -ob_fr, "", ""),
        ("  Escalation adj.",             -esc,   "", ""),
        ("  Contingency",                 -cont,  "", ""),
        ("Gross margin",                   gm,    gm, f"{gm/sell*100:.1f}%" if sell else "—"),
        ("Margin (commercial)",            margin, margin, f"{margin/sell*100:.1f}%" if sell else "—"),
    ]

    return pd.DataFrame(rows, columns=["Item", "€ (run)", "Running €", "Note"])
