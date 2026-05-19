from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import pandas as pd


def check_missing(df: pd.DataFrame, required: Iterable[str]) -> List[str]:
    req = list(required)
    return [c for c in req if c not in df.columns]


def check_positive(df: pd.DataFrame, cols: Iterable[str]) -> List[str]:
    bad = []
    for c in cols:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if (s <= 0).any():
            bad.append(c)
    return bad


@dataclass(frozen=True)
class Rule:
    name: str
    ok: bool
    msg: str


def within(df: pd.DataFrame, col: str, lo: float | None, hi: float | None) -> bool:
    if col not in df.columns:
        return False
    s = pd.to_numeric(df[col], errors="coerce")
    good = True
    if lo is not None:
        good &= (s >= lo).all()
    if hi is not None:
        good &= (s <= hi).all()
    return bool(good)


def material_lines(bom: pd.DataFrame) -> pd.DataFrame:
    """BOM rows that reference a physical material (excludes service/assembly/NDT lines)."""
    if "material_id" not in bom.columns:
        return bom
    has_mat = bom["material_id"].notna() & (bom["material_id"].astype(str).str.strip() != "")
    return bom[has_mat]


def business_rules(mats: pd.DataFrame, procs: pd.DataFrame, bom: pd.DataFrame) -> List[Rule]:
    mat_bom = material_lines(bom)   # service lines excluded from physical checks
    rules: List[Rule] = []
    rules.append(
        Rule(
            "rates_positive",
            within(procs, "machine_rate_eur_h", 0.01, None)
            and within(procs, "labor_rate_eur_h", 0.01, None),
            "Machine- en arbeidsloon moeten > 0 zijn.",
        )
    )
    rules.append(
        Rule(
            "overhead_pct_range",
            within(procs, "overhead_pct", 0.0, 1.0),
            "overhead_pct moet tussen 0 en 1 liggen.",
        )
    )
    rules.append(
        Rule(
            "margin_pct_range",
            within(procs, "margin_pct", 0.0, 1.0),
            "margin_pct moet tussen 0 en 1 liggen.",
        )
    )
    rules.append(Rule("qty_min_1",    within(mat_bom, "qty",      1,         None), "qty moet >= 1 zijn."))
    rules.append(Rule("mass_positive", within(mat_bom, "mass_kg",  0.000001, None), "mass_kg moet > 0 zijn."))
    rules.append(Rule("runtime_nonneg", within(bom,    "runtime_h", 0.0,     None), "runtime_h moet >= 0 zijn."))
    rules.append(
        Rule(
            "mat_price_pos",
            within(mats, "price_eur_per_kg", 0.000001, None),
            "Materiaalprijs moet > 0 zijn.",
        )
    )
    return rules


def summarize_rules(rules: Sequence[Rule]) -> str:
    return "\n".join(
        ("✅ " if r.ok else "❌ ") + f"{r.name}: " + ("OK" if r.ok else r.msg) for r in rules
    )


def all_rules_ok(rules: Sequence[Rule]) -> bool:
    return all(r.ok for r in rules)
