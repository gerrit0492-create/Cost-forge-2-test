"""
Learning curve and volume analysis utilities.
Implements Wright's Law for manufacturing cost reduction with volume.
"""
from __future__ import annotations

import math
import pandas as pd


def wright_unit_cost(cost_at_1: float, learning_rate: float, qty: int) -> float:
    """
    Unit cost at cumulative quantity `qty` using Wright's Law.

    Parameters
    ----------
    cost_at_1 : float
        Unit cost at quantity = 1 (first article cost).
    learning_rate : float
        Fraction retained on each doubling; 0.85 = 15% reduction per doubling.
    qty : int
        Cumulative production quantity (≥ 1).
    """
    if qty <= 0 or cost_at_1 <= 0 or learning_rate <= 0:
        return cost_at_1
    b = math.log(learning_rate) / math.log(2)
    return cost_at_1 * (qty ** b)


def wright_cumulative_average(cost_at_1: float, learning_rate: float, qty: int) -> float:
    """Cumulative average unit cost over a run of `qty` units."""
    if qty <= 1:
        return cost_at_1
    b = math.log(learning_rate) / math.log(2)
    # Approximation: C_avg = C1 * n^b / (1 + b)
    return cost_at_1 * (qty ** b) / (1 + b)


def batch_cost_table(
    base_unit_cost: float,
    learning_rate: float,
    quantities: list[int],
    fixed_nre: float = 0.0,
    setup_cost_per_batch: float = 0.0,
) -> pd.DataFrame:
    """
    Build a cost table across a range of production quantities.

    Returns DataFrame with columns:
        qty, unit_cost, total_direct, nre_amortised, setup_amortised,
        all_in_per_unit, all_in_total, vs_qty1_pct
    """
    rows = []
    cost_at_1 = base_unit_cost
    for q in sorted(set(quantities)):
        if q < 1:
            continue
        unit = wright_unit_cost(cost_at_1, learning_rate, q)
        total_direct = unit * q
        nre_amt  = fixed_nre / q if q > 0 else fixed_nre
        setup_amt = setup_cost_per_batch / q if q > 0 else 0
        all_in   = unit + nre_amt + setup_amt
        rows.append({
            "qty":              q,
            "unit_cost":        round(unit, 2),
            "total_direct":     round(total_direct, 2),
            "nre_amortised":    round(nre_amt, 2),
            "setup_amortised":  round(setup_amt, 2),
            "all_in_per_unit":  round(all_in, 2),
            "all_in_total":     round(all_in * q, 2),
            "vs_qty1_pct":      round((all_in / (cost_at_1 + fixed_nre) - 1) * 100, 1)
                                if (cost_at_1 + fixed_nre) > 0 else 0,
        })
    return pd.DataFrame(rows)


def optimal_qty_for_target(
    base_unit_cost: float,
    learning_rate: float,
    target_unit_cost: float,
    fixed_nre: float = 0.0,
    max_qty: int = 10_000,
) -> int | None:
    """Return first quantity where all-in unit cost ≤ target_unit_cost."""
    b = math.log(learning_rate) / math.log(2) if learning_rate > 0 else 0
    for q in range(1, max_qty + 1):
        unit  = base_unit_cost * (q ** b)
        all_in = unit + (fixed_nre / q)
        if all_in <= target_unit_cost:
            return q
    return None


def learning_curve_series(
    cost_at_1: float,
    learning_rate: float,
    max_qty: int = 100,
) -> pd.DataFrame:
    """Return a dense series suitable for a smooth line chart."""
    qs = list(range(1, min(max_qty + 1, 201)))
    b  = math.log(learning_rate) / math.log(2)
    return pd.DataFrame({
        "qty":       qs,
        "unit_cost": [round(cost_at_1 * (q ** b), 2) for q in qs],
    })
