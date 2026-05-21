"""
Contract management, milestone payment schedules, commercial terms and cash flow.
"""
from __future__ import annotations
import pandas as pd

SCHEMA_CONTRACT_META = {
    # Single-row config stored in project.json, not Excel
    # contract_number, customer, contract_value_eur, signing_date, delivery_date,
    # warranty_months, ld_pct_per_week, ld_cap_pct, retention_pct,
    # apg_required, apg_fee_pct, bond_required, bond_pct, bond_fee_pct,
    # energy_rate_eur_kwh, subcontract_markup_pct
}

SCHEMA_MILESTONES = {
    "milestone_id":    "string",
    "description":     "string",   # e.g. "Advance payment", "FAT", "Delivery", "Warranty release"
    "trigger_event":   "string",   # e.g. "Contract signature", "Factory Acceptance Test"
    "pct_of_contract": "float64",  # e.g. 0.30 = 30%
    "amount_eur":      "float64",  # auto-computed but editable
    "planned_date":    "string",   # ISO date
    "actual_date":     "string",   # ISO date, blank if not yet received
    "received":        "string",   # "Yes" / "No" / ""
    "notes":           "string",
}

SCHEMA_COST_TIMELINE = {
    "cost_id":       "string",
    "category":      "string",   # Material / Process / NRE / Transport / Other
    "description":   "string",
    "amount_eur":    "float64",
    "planned_date":  "string",   # ISO date when this cost is incurred/paid
    "actual_date":   "string",
    "paid":          "string",   # Yes/No
    "notes":         "string",
}

INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]
WARRANTY_OPTIONS = [6, 12, 18, 24, 36]


def default_milestones(contract_value: float = 0.0) -> pd.DataFrame:
    """Return a standard marine capital equipment milestone schedule."""
    milestones = [
        ("M-01", "Advance payment",      "Contract signature",           0.30),
        ("M-02", "Progress payment",     "Completion of main machining", 0.30),
        ("M-03", "Delivery payment",     "Factory Acceptance Test",      0.30),
        ("M-04", "Warranty release",     "End of warranty period",       0.10),
    ]
    rows = []
    for mid, desc, trigger, pct in milestones:
        rows.append({
            "milestone_id":    mid,
            "description":     desc,
            "trigger_event":   trigger,
            "pct_of_contract": pct,
            "amount_eur":      round(contract_value * pct, 2),
            "planned_date":    "",
            "actual_date":     "",
            "received":        "No",
            "notes":           "",
        })
    return pd.DataFrame(rows)


def cash_flow_series(
    milestones: pd.DataFrame,
    cost_timeline: pd.DataFrame,
    project_start: str,
    project_end: str,
) -> pd.DataFrame:
    """
    Build monthly cash flow from milestone payments (receipts) and cost timeline (outflows).
    Returns DataFrame with columns: month, receipts, costs, net, cumulative.
    """
    try:
        start = pd.Timestamp(project_start)
        end   = pd.Timestamp(project_end)
    except Exception:
        return pd.DataFrame(columns=["month", "receipts", "costs", "net", "cumulative"])

    months = pd.date_range(start, end, freq="MS")
    result = pd.DataFrame({"month": months, "receipts": 0.0, "costs": 0.0})

    # Add milestone receipts
    for _, row in milestones.iterrows():
        date_str = row.get("actual_date") or row.get("planned_date") or ""
        if not date_str:
            continue
        try:
            d = pd.Timestamp(date_str)
            idx = result[
                (result["month"].dt.year == d.year) &
                (result["month"].dt.month == d.month)
            ].index
            if not idx.empty:
                amt = float(row.get("amount_eur") or 0)
                result.loc[idx[0], "receipts"] += amt
        except Exception:
            continue

    # Add cost outflows
    for _, row in cost_timeline.iterrows():
        date_str = row.get("actual_date") or row.get("planned_date") or ""
        if not date_str:
            continue
        try:
            d = pd.Timestamp(date_str)
            idx = result[
                (result["month"].dt.year == d.year) &
                (result["month"].dt.month == d.month)
            ].index
            if not idx.empty:
                amt = float(row.get("amount_eur") or 0)
                result.loc[idx[0], "costs"] += amt
        except Exception:
            continue

    result["net"]        = result["receipts"] - result["costs"]
    result["cumulative"] = result["net"].cumsum()
    return result


def apg_cost(advance_amount: float, apg_fee_pct: float, months: int) -> float:
    """Annual APG fee prorated to months."""
    return advance_amount * apg_fee_pct * (months / 12)


def bond_cost(contract_value: float, bond_pct: float, bond_fee_pct: float, months: int) -> float:
    return contract_value * bond_pct * bond_fee_pct * (months / 12)


def ld_exposure(contract_value: float, ld_pct_per_week: float, ld_cap_pct: float, delay_weeks: int) -> float:
    """Maximum LD liability for given delay."""
    ld  = contract_value * ld_pct_per_week * delay_weeks
    cap = contract_value * ld_cap_pct
    return min(ld, cap)


def retention_amount(contract_value: float, retention_pct: float) -> float:
    return contract_value * retention_pct


def working_capital_peak(cash_flow_df: pd.DataFrame) -> tuple[float, str]:
    """Return (peak WC need, month string). Peak WC = most negative cumulative position."""
    if cash_flow_df.empty:
        return 0.0, "—"
    min_idx = cash_flow_df["cumulative"].idxmin()
    peak    = float(cash_flow_df.loc[min_idx, "cumulative"])
    month   = str(cash_flow_df.loc[min_idx, "month"])[:7] if min_idx is not None else "—"
    return (abs(peak) if peak < 0 else 0.0), month
