# tools/update_materials_from_market.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

DATA = Path("data")
HISTORY = DATA / "history"
MATS_CSV = DATA / "materials_db.csv"
QUOTES_CSV = DATA / "supplier_quotes.csv"
FACTORS_CSV = DATA / "market_factors.csv"            # optioneel
FACTORS_URL_FILE = DATA / "market_factors_url.txt"   # app schrijft hier de URL

# Alleen loggen (niet blokkeren) boven deze drempel
ANOMALY_LOG_THR = 0.25  # 25%

def _read_csv_safe(p: Path, req: Optional[list[str]] = None) -> Optional[pd.DataFrame]:
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if req:
        missing = [c for c in req if c not in df.columns]
        if missing:
            raise ValueError(f"{p}: ontbrekende kolommen: {missing}")
    return df

def _read_market_factors() -> Optional[pd.DataFrame]:
    if FACTORS_URL_FILE.exists():
        url = FACTORS_URL_FILE.read_text(encoding="utf-8").strip()
        if url:
            try:
                return pd.read_csv(url, comment="#")
            except Exception as e:
                print(f"⚠️ Kon URL uit {FACTORS_URL_FILE} niet lezen: {e}")
    if FACTORS_CSV.exists():
        try:
            return pd.read_csv(FACTORS_CSV, comment="#")
        except Exception as e:
            print(f"⚠️ Kon {FACTORS_CSV} niet lezen: {e}")
    return None

def best_quotes(quotes: pd.DataFrame) -> pd.DataFrame:
    q = quotes.copy()
    if "preferred" not in q.columns:
        q["preferred"] = 0
    if "lead_time_days" not in q.columns:
        q["lead_time_days"] = 999_999
    q = q.sort_values(
        by=["material_id","preferred","price_eur_per_kg","lead_time_days"],
        ascending=[True,False,True,True],
        kind="mergesort",
    )
    return q.groupby("material_id", as_index=False).first()

def apply_best_quotes_to_materials(mats: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    bq = best_quotes(quotes)[["material_id","price_eur_per_kg"]].rename(columns={"price_eur_per_kg":"price_from_quote"})
    out = mats.merge(bq, on="material_id", how="left")
    if "price_eur_per_kg" not in out.columns:
        out["price_eur_per_kg"] = out["price_from_quote"]
    else:
        out["price_eur_per_kg"] = pd.to_numeric(out["price_eur_per_kg"], errors="coerce").fillna(out["price_from_quote"])
    return out.drop(columns=["price_from_quote"])

def apply_market_factors(mats: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    out = mats.copy()
    f = factors.copy()
    f.columns = [c.strip().lower() for c in f.columns]
    has_cmd = "commodity" in out.columns and "commodity" in f.columns

    by_mat, by_cmd = {}, {}
    if "material_id" in f.columns:
        for _, r in f.iterrows():
            k = r.get("material_id")
            if pd.notna(k):
                by_mat[str(k)] = r
    if has_cmd:
        for _, r in f.iterrows():
            k = r.get("commodity")
            if pd.notna(k):
                by_cmd[str(k)] = r

    def _apply(price: float, r: pd.Series) -> float:
        v = price
        pct, fac = r.get("pct_change"), r.get("factor")
        if pd.notna(pct):
            try:
                v *= 1 + float(pct) / 100.0
            except Exception:
                pass
        if pd.notna(fac):
            try:
                v *= float(fac)
            except Exception:
                pass
        return v

    for i in range(len(out)):
        base = out.at[i, "price_eur_per_kg"]
        if pd.isna(base):
            continue
        mid = str(out.at[i, "material_id"])
        if mid in by_mat:
            out.at[i, "price_eur_per_kg"] = _apply(base, by_mat[mid])
        elif has_cmd:
            cmd = str(out.at[i, "commodity"])
            if cmd in by_cmd:
                out.at[i, "price_eur_per_kg"] = _apply(base, by_cmd[cmd])
    return out

def _save_history(df: pd.DataFrame, label: str) -> Path:
    HISTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    p = HISTORY / f"materials_{stamp}.csv"
    if not p.exists():
        df.to_csv(p, index=False)
        print(f"🗂️ Snapshot ({label}): {p}")
    else:
        print(f"ℹ️ Snapshot ({label}) bestond al: {p}")
    return p

def _anomaly_log(before: pd.DataFrame, after: pd.DataFrame, thr: float) -> None:
    if "material_id" not in before.columns or "material_id" not in after.columns:
        return
    b = before.set_index("material_id")
    a = after.set_index("material_id")
    common = b.index.intersection(a.index)
    rows = []
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
            rows.append({"material_id": mid, "old_price": old, "new_price": new, "pct_change": pct})
    if rows:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        p = HISTORY / f"anomalies_update_{ts}.csv"
        pd.DataFrame(rows).sort_values("pct_change").to_csv(p, index=False)
        print(f"📝 Anomaly-log: {p} (>{thr*100:.1f}%)")

def main():
    mats = _read_csv_safe(MATS_CSV, ["material_id","description","price_eur_per_kg"])
    if mats is None or mats.empty:
        raise SystemExit("materials_db.csv ontbreekt of is leeg")

    before = mats.copy()

    quotes = _read_csv_safe(QUOTES_CSV, ["supplier","material_id","price_eur_per_kg","lead_time_days","valid_until","preferred"])
    if quotes is not None and not quotes.empty:
        mats = apply_best_quotes_to_materials(mats, quotes)

    factors = _read_market_factors()
    if factors is not None and not factors.empty:
        mats = apply_market_factors(mats, factors)

    if "price_eur_per_kg" in mats.columns:
        mats["price_eur_per_kg"] = pd.to_numeric(mats["price_eur_per_kg"], errors="coerce").round(4)

    # snapshot voor & na
    if not before.empty:
        _save_history(before, "before")
    changed = True
    try:
        changed = not mats.equals(before)
    except Exception:
        changed = True

    if changed:
        mats.to_csv(MATS_CSV, index=False)
        print("✅ materials_db.csv bijgewerkt.")
        _anomaly_log(before, mats, ANOMALY_LOG_THR)
    else:
        print("ℹ️ Geen prijswijzigingen.")
    _save_history(mats, "after")

if __name__ == "__main__":
    main()
