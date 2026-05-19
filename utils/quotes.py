import pandas as pd


def expired_quote_materials(quotes: pd.DataFrame) -> list[str]:
    """Return material_ids whose best quote has expired."""
    if "valid_until" not in quotes.columns:
        return []
    today = pd.Timestamp.today().normalize()
    expired = quotes[pd.to_datetime(quotes["valid_until"], errors="coerce") < today]
    return sorted(expired["material_id"].unique().tolist())


def best_quotes(quotes: pd.DataFrame) -> pd.DataFrame:
    q = quotes.copy()
    q["preferred"] = q.get("preferred", 0)
    q["lead_time_days"] = q.get("lead_time_days", 999_999)
    # Drop expired quotes before ranking
    if "valid_until" in q.columns:
        today = pd.Timestamp.today().normalize()
        valid_mask = pd.to_datetime(q["valid_until"], errors="coerce") >= today
        q = q[valid_mask]
    q = q.sort_values(
        by=["material_id", "preferred", "price_eur_per_kg", "lead_time_days"],
        ascending=[True, False, True, True],
    )
    return q.groupby("material_id").head(1).reset_index(drop=True)


def apply_best_quotes(materials: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    best = best_quotes(quotes)
    m = materials.merge(
        best[["material_id", "price_eur_per_kg", "supplier", "lead_time_days"]],
        on="material_id",
        how="left",
        suffixes=("_base", "_quote"),
    )
    # Prefer negotiated supplier price; fall back to materials catalogue price
    if "price_eur_per_kg_quote" in m.columns:
        base_col = "price_eur_per_kg_base" if "price_eur_per_kg_base" in m.columns else "price_eur_per_kg"
        m["price_eur_per_kg"] = m["price_eur_per_kg_quote"].fillna(m[base_col])
        m = m.drop(columns=[c for c in ["price_eur_per_kg_base", "price_eur_per_kg_quote"] if c in m.columns])
    return m


def join_with_materials(materials: pd.DataFrame, best: pd.DataFrame) -> pd.DataFrame:
    return materials.drop(columns=["price_eur_per_kg"], errors="ignore").merge(
        best[["material_id", "supplier", "price_eur_per_kg", "lead_time_days"]],
        on="material_id",
        how="left",
    )
