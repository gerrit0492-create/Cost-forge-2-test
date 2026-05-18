# utils/history.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Paden
DATA_DIR = Path("data")
HISTORY_DIR = DATA_DIR / "history"
MATERIALS_CSV = DATA_DIR / "materials_db.csv"

# --- Proxy naar utils.io zodat bestaande imports blijven werken ---
try:
    # load_* en schema's blijven beschikbaar via deze module
    from utils.io import (
        SCHEMA_MATERIALS,
    )
    from utils.io import (
        load_materials as _load_materials_io,
    )
except Exception:
    logger.warning("utils.io not available; falling back to direct CSV read", exc_info=True)
    _load_materials_io = None  # type: ignore
    SCHEMA_MATERIALS = {
        "material_id": "string",
        "description": "string",
        "price_eur_per_kg": "float64",
    }


def load_materials() -> pd.DataFrame:
    """Proxy: hou bestaande import 'from utils.history import load_materials' werkend."""
    if _load_materials_io is None:
        return pd.read_csv(MATERIALS_CSV)
    return _load_materials_io()


# --- Snapshots utilities -------------------------------------------------------

_SNAP_RE = re.compile(r"materials_(\d{8})\.csv$", re.IGNORECASE)


def list_snapshots() -> List[Path]:
    """Alle materials-snapshots op datum (oplopend gesorteerd)."""
    if not HISTORY_DIR.exists():
        return []
    snaps = [p for p in HISTORY_DIR.glob("materials_*.csv") if _SNAP_RE.search(p.name)]
    return sorted(snaps, key=lambda p: p.name)


def latest_snapshot() -> Optional[Path]:
    snaps = list_snapshots()
    return snaps[-1] if snaps else None


def _date_from_name(p: Path) -> Optional[datetime]:
    m = _SNAP_RE.search(p.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d")


def save_snapshot_current() -> Path:
    """Sla huidige materials op als materials_YYYYMMDD.csv (overschrijft niet)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow().strftime("%Y%m%d")
    out = HISTORY_DIR / f"materials_{today}.csv"
    if not out.exists():
        df = load_materials()
        df.to_csv(out, index=False)
    return out


# --- Historie opbouwen ---------------------------------------------------------


def build_history_df(material_ids: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """
    Bouw een lange tabel met kolommen:
      date (datetime64), material_id, price_eur_per_kg, description, commodity (optioneel)
    """
    rows: List[dict] = []
    snaps = list_snapshots()
    if not snaps:
        return pd.DataFrame(
            columns=["date", "material_id", "price_eur_per_kg", "description", "commodity"]
        )

    want = set(str(x) for x in material_ids) if material_ids else None

    for p in snaps:
        dt = _date_from_name(p)
        if dt is None:
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            logger.warning("Skipping corrupt snapshot: %s", p, exc_info=True)
            continue

        # Normaliseer kolommen
        for col in ["material_id", "description", "commodity", "price_eur_per_kg"]:
            if col not in df.columns:
                if col == "price_eur_per_kg":
                    df[col] = pd.NA
                else:
                    df[col] = ""

        if want:
            df = df[df["material_id"].astype(str).isin(want)]

        for _, r in df.iterrows():
            rows.append(
                dict(
                    date=dt,
                    material_id=str(r["material_id"]),
                    description=str(r["description"]),
                    commodity=str(r["commodity"]),
                    price_eur_per_kg=pd.to_numeric(r["price_eur_per_kg"], errors="coerce"),
                )
            )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["material_id", "date"]).reset_index(drop=True)
    return out


def get_price_series(material_id: str) -> pd.DataFrame:
    """Geschiedenis voor één materiaal (date, price_eur_per_kg)."""
    df = build_history_df([material_id])
    if df.empty:
        return df
    return df[["date", "price_eur_per_kg"]].sort_values("date")


# --- Diffs & controles ---------------------------------------------------------


def diff_vs_latest() -> pd.DataFrame:
    """
    Vergelijk current materials_db.csv met laatste snapshot.
    Geeft: material_id, old_price, new_price, pct_change
    """
    snap = latest_snapshot()
    if snap is None or not MATERIALS_CSV.exists():
        return pd.DataFrame(columns=["material_id", "old_price", "new_price", "pct_change"])

    current = pd.read_csv(MATERIALS_CSV)
    prev = pd.read_csv(snap)

    # Alleen nodige kolommen
    for df in (current, prev):
        for col in ["material_id", "price_eur_per_kg"]:
            if col not in df.columns:
                df[col] = pd.NA

    c = current[["material_id", "price_eur_per_kg"]].copy()
    p = prev[["material_id", "price_eur_per_kg"]].copy()
    c["price_eur_per_kg"] = pd.to_numeric(c["price_eur_per_kg"], errors="coerce")
    p["price_eur_per_kg"] = pd.to_numeric(p["price_eur_per_kg"], errors="coerce")

    m = p.merge(c, on="material_id", suffixes=("_old", "_new"), how="outer")
    old_nonzero = m["price_eur_per_kg_old"].replace(0, pd.NA)
    m["pct_change"] = (m["price_eur_per_kg_new"] - m["price_eur_per_kg_old"]) / old_nonzero
    m = m.rename(columns={"price_eur_per_kg_old": "old_price", "price_eur_per_kg_new": "new_price"})
    return m


@dataclass
class AnomalyConfig:
    threshold_pct: float = 0.25  # 25%
    min_anomalies: int = 10


def find_anomalies(df_diff: pd.DataFrame, cfg: AnomalyConfig = AnomalyConfig()) -> pd.DataFrame:
    """Filter regels met abs(pct_change) > threshold."""
    if df_diff.empty or "pct_change" not in df_diff.columns:
        return pd.DataFrame(columns=df_diff.columns)
    a = df_diff.copy()
    a = a[pd.notna(a["pct_change"])]
    a["abs_pct"] = a["pct_change"].abs()
    return a[a["abs_pct"] > cfg.threshold_pct].sort_values("abs_pct", ascending=False)
