# tools/restore_materials_from_history.py
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

DATA = Path("data")
HISTORY = DATA / "history"
MATS = DATA / "materials_db.csv"

# ── Guardrail parameters (via env met defaults) ────────────────────────────────
# Percentage-drempel als fractie: 0.4 = 40%
THRESHOLD_PCT = float(os.getenv("THRESHOLD_PCT", "0.40"))
# Minimaal aantal hits boven drempel om te blokkeren
MIN_ANOMALIES = int(os.getenv("MIN_ANOMALIES", "10"))
# Forceer overschrijven ondanks anomaliën
FORCE = os.getenv("FORCE", "false").strip().lower() == "true"

def pick_snapshot(arg: Optional[str]) -> Path:
    if not HISTORY.exists():
        raise FileNotFoundError(f"Geen history map: {HISTORY}")
    snaps = sorted(HISTORY.glob("materials_*.csv"))
    if not snaps:
        raise FileNotFoundError("Geen snapshots gevonden in data/history/")
    if not arg or arg.lower() == "latest":
        return snaps[-1]
    arg = arg.strip()
    if arg.endswith(".csv"):
        p = HISTORY / arg
        if not p.exists():
            raise FileNotFoundError(f"Snapshot bestaat niet: {p}")
        return p
    p = HISTORY / f"materials_{arg}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Snapshot bestaat niet: {p}")
    return p

def show_diff(before: pd.DataFrame, after: pd.DataFrame) -> str:
    def keyset(df: pd.DataFrame):
        return set(df["material_id"].astype(str)) if "material_id" in df.columns else set()
    kb, ka = keyset(before), keyset(after)
    added, removed = sorted(list(ka - kb)), sorted(list(kb - ka))
    changed = []
    b, a = before.set_index("material_id"), after.set_index("material_id")
    common = sorted(list(kb & ka))
    fields = ["price_eur_per_kg", "commodity", "description"]
    for mid in common:
        vb, va = b.loc[mid].to_dict(), a.loc[mid].to_dict()
        diffs = [f"{f}: {vb.get(f)} -> {va.get(f)}" for f in fields if vb.get(f) != va.get(f)]
        if diffs:
            changed.append(f"{mid}: " + "; ".join(diffs))
    out = [
        f"Toegevoegd: {len(added)} | Verwijderd: {len(removed)} | Gewijzigd: {len(changed)}",
    ]
    if added:
        out.append(" + " + ", ".join(added[:10]) + (" …" if len(added) > 10 else ""))
    if removed:
        out.append(" - " + ", ".join(removed[:10]) + (" …" if len(removed) > 10 else ""))
    if changed:
        out.append(" ~ " + " | ".join(changed[:5]) + (" …" if len(changed) > 5 else ""))
    return "\n".join(out)

def anomaly_scan(before: pd.DataFrame, after: pd.DataFrame, thr: float) -> Tuple[pd.DataFrame, int]:
    """Return (anomalies_df, count) voor abs(pct change) > thr"""
    if "material_id" not in before.columns or "material_id" not in after.columns:
        return pd.DataFrame(), 0
    b = before.set_index("material_id")
    a = after.set_index("material_id")
    common = b.index.intersection(a.index)
    out = []
    for mid in common:
        try:
            old = float(pd.to_numeric(b.loc[mid, "price_eur_per_kg"], errors="coerce"))
            new = float(pd.to_numeric(a.loc[mid, "price_eur_per_kg"], errors="coerce"))
        except Exception:
            continue
        if not pd.notna(old) or not pd.notna(new) or old == 0:
            continue
        pct = (new - old) / old
        if abs(pct) > thr:
            out.append(
                {
                    "material_id": mid,
                    "old_price": old,
                    "new_price": new,
                    "pct_change": pct,
                    "abs_pct": abs(pct),
                }
            )
    df = pd.DataFrame(out).sort_values("abs_pct", ascending=False)
    return df, len(df)

def write_anomalies(df: pd.DataFrame, tag: str) -> Optional[Path]:
    if df.empty:
        return None
    HISTORY.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    p = HISTORY / f"anomalies_restore_{tag}_{ts}.csv"
    df.to_csv(p, index=False)
    return p

def main():
    snap_arg = os.getenv("SNAPSHOT", "latest")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    snap = pick_snapshot(snap_arg)
    print(f"🔎 Snapshot: {snap}")

    if not MATS.exists():
        raise FileNotFoundError(f"{MATS} ontbreekt; niets om te overschrijven.")

    before = pd.read_csv(MATS)
    after = pd.read_csv(snap)

    # sanity
    req = {"material_id", "price_eur_per_kg"}
    miss = req - set(after.columns)
    if miss:
        raise ValueError(f"Snapshot mist verplichte kolommen: {miss}")

    # diff en anomaly-scan
    print("=== DIFF SAMENVATTING ===")
    print(show_diff(before, after))

    anomalies, count = anomaly_scan(before, after, THRESHOLD_PCT)
    if count:
        print(f"🚧 Anomaliën > {THRESHOLD_PCT*100:.1f}%: {count}")
        apath = write_anomalies(anomalies, "preview" if dry_run else "preapply")
        if apath:
            print(f"↳ details: {apath}")

    if dry_run:
        print("🧪 Dry-run: geen wijzigingen geschreven.")
        return

    if count >= MIN_ANOMALIES and not FORCE:
        msg = (
            f"⛔ Restore geblokkeerd: {count} anomaliën > {THRESHOLD_PCT*100:.1f}% "
            f"(min={MIN_ANOMALIES}). Zet FORCE=true om te forceren."
        )
        print(msg)
        sys.exit(2)

    # schrijf
    after.to_csv(MATS, index=False)
    print(f"✅ Hersteld materials_db.csv vanaf {snap.name}")

    # log na-anomalieën (ter referentie)
    anomalies_after, count_after = anomaly_scan(before, after, THRESHOLD_PCT)
    if count_after:
        apath2 = write_anomalies(anomalies_after, "applied")
        if apath2:
            print(f"📝 Anomaly-log na restore: {apath2}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
