from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import load_materials, load_quotes
from utils.nav import home_button
from utils.quotes import apply_best_quotes, best_quotes
from utils.safe import guard


def main() -> None:
    st.set_page_config(page_title="Materials", layout="wide", page_icon="🧱")
    home_button()
    st.title("🧱 Material Library")
    st.caption("Browse and analyse the material library — prices, commodities, supplier coverage and cost exposure.")

    _, btn = st.columns([6, 1])
    if btn.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    mats   = load_materials()
    quotes = load_quotes()

    if mats.empty:
        st.info("No materials found. Import via **CSV Import** or edit `data/cost_forge.xlsx`.")
        return

    # Enrich with best quote
    if not quotes.empty:
        best = best_quotes(quotes)
        enriched = mats.merge(
            best[["material_id", "supplier", "price_eur_per_kg", "valid_until", "lead_time_days"]
                 if "lead_time_days" in best.columns else
                 [c for c in ["material_id", "supplier", "price_eur_per_kg", "valid_until"] if c in best.columns]],
            on="material_id", how="left", suffixes=("_base", "_quote"),
        )
        # Use quote price where available, fall back to base
        if "price_eur_per_kg_quote" in enriched.columns:
            enriched["effective_price"] = enriched["price_eur_per_kg_quote"].fillna(
                enriched.get("price_eur_per_kg_base", enriched.get("price_eur_per_kg", 0))
            )
            enriched["has_quote"] = enriched["price_eur_per_kg_quote"].notna()
        else:
            enriched["effective_price"] = enriched.get("price_eur_per_kg", 0)
            enriched["has_quote"] = False
    else:
        enriched = mats.copy()
        enriched["effective_price"] = enriched.get("price_eur_per_kg", 0)
        enriched["has_quote"] = False
        enriched["supplier"] = None

    today = pd.Timestamp.today().normalize()
    if "valid_until" in enriched.columns:
        enriched["valid_until"] = pd.to_datetime(enriched["valid_until"], errors="coerce")
        enriched["quote_status"] = enriched.apply(
            lambda r: ("🔴 Expired" if pd.notna(r["valid_until"]) and r["valid_until"] < today
                       else ("🟢 Valid" if r["has_quote"] else "⚪ No quote")),
            axis=1,
        )
    else:
        enriched["quote_status"] = enriched["has_quote"].map(
            lambda x: "🟢 Valid" if x else "⚪ No quote"
        )

    # ── KPI strip ─────────────────────────────────────────────────────────────
    n_mats     = len(enriched)
    n_quoted   = int(enriched["has_quote"].sum())
    n_no_quote = n_mats - n_quoted
    avg_price  = enriched["effective_price"].mean()
    max_price  = enriched["effective_price"].max()

    commodities = enriched["commodity"].nunique() if "commodity" in enriched.columns else "—"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total materials",   n_mats)
    k2.metric("With valid quote",  n_quoted,
              delta=f"{n_quoted/n_mats*100:.0f}% coverage" if n_mats else "—",
              delta_color="off")
    k3.metric("No valid quote",    n_no_quote,
              delta="action needed" if n_no_quote else "all covered",
              delta_color="inverse" if n_no_quote else "off")
    k4.metric("Avg price",         fmt(avg_price, 2) + "/kg")
    k5.metric("Commodity groups",  commodities)

    st.divider()

    tab_browser, tab_prices, tab_commodity, tab_coverage = st.tabs([
        "📋 Material browser",
        "💰 Price ranking",
        "🏷️ By commodity",
        "✅ Quote coverage",
    ])

    # ── Material browser ──────────────────────────────────────────────────────
    with tab_browser:
        st.subheader("Material library")

        # Filters
        f1, f2, f3 = st.columns(3)
        search = f1.text_input("Search material ID", placeholder="e.g. NAB, 316L…")
        if "commodity" in enriched.columns:
            comms = ["All"] + sorted(enriched["commodity"].dropna().unique().tolist())
            sel_comm = f2.selectbox("Commodity", comms)
        else:
            sel_comm = "All"
        if "quote_status" in enriched.columns:
            statuses = ["All"] + sorted(enriched["quote_status"].unique().tolist())
            sel_status = f3.selectbox("Quote status", statuses)
        else:
            sel_status = "All"

        filt = enriched.copy()
        if search:
            filt = filt[filt["material_id"].str.contains(search, case=False, na=False)]
        if sel_comm != "All" and "commodity" in filt.columns:
            filt = filt[filt["commodity"] == sel_comm]
        if sel_status != "All" and "quote_status" in filt.columns:
            filt = filt[filt["quote_status"] == sel_status]

        display_cols = ["material_id", "quote_status"]
        if "commodity"       in filt.columns: display_cols.append("commodity")
        if "supplier"        in filt.columns: display_cols.append("supplier")
        display_cols.append("effective_price")
        if "valid_until"     in filt.columns: display_cols.append("valid_until")
        if "lead_time_days"  in filt.columns: display_cols.append("lead_time_days")

        show = filt[[c for c in display_cols if c in filt.columns]].copy()
        if "effective_price" in show.columns:
            show["effective_price"] = show["effective_price"].map(lambda x: fmt(x, 2))
        if "valid_until" in show.columns:
            show["valid_until"] = pd.to_datetime(show["valid_until"]).dt.strftime("%d %b %Y")

        st.dataframe(
            show.rename(columns={
                "material_id":    "Material",
                "quote_status":   "Status",
                "commodity":      "Commodity",
                "supplier":       "Supplier",
                "effective_price":"Best price €/kg",
                "valid_until":    "Valid until",
                "lead_time_days": "Lead time (d)",
            }),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Showing {len(show)} of {len(enriched)} materials.")

    # ── Price ranking ──────────────────────────────────────────────────────────
    with tab_prices:
        st.subheader("Price per kg — material ranking")
        ranked = enriched[["material_id", "effective_price"]].sort_values(
            "effective_price", ascending=False
        ).copy()
        if "commodity" in enriched.columns:
            ranked = ranked.merge(enriched[["material_id", "commodity"]], on="material_id", how="left")
        if "supplier" in enriched.columns:
            ranked = ranked.merge(enriched[["material_id", "supplier"]], on="material_id", how="left")

        pr1, pr2 = st.columns([2, 1])
        with pr1:
            st.bar_chart(
                ranked.set_index("material_id")[["effective_price"]].rename(
                    columns={"effective_price": "Price €/kg"}
                ),
                color="#FF9800",
            )
        with pr2:
            disp = ranked.copy()
            disp["effective_price"] = disp["effective_price"].map(lambda x: fmt(x, 2))
            st.dataframe(
                disp.rename(columns={
                    "material_id": "Material", "effective_price": "Price €/kg",
                    "commodity": "Commodity", "supplier": "Supplier",
                }),
                use_container_width=True, hide_index=True,
            )

    # ── By commodity ──────────────────────────────────────────────────────────
    with tab_commodity:
        if "commodity" not in enriched.columns:
            st.info("No `commodity` column in material data.")
        else:
            st.subheader("Materials by commodity group")
            comm_grp = (
                enriched.groupby("commodity").agg(
                    count=("material_id", "count"),
                    avg_price=("effective_price", "mean"),
                    min_price=("effective_price", "min"),
                    max_price=("effective_price", "max"),
                ).reset_index().sort_values("avg_price", ascending=False)
            )

            cg1, cg2 = st.columns([2, 1])
            with cg1:
                st.bar_chart(
                    comm_grp.set_index("commodity")[["avg_price"]].rename(
                        columns={"avg_price": "Avg price €/kg"}
                    ),
                    color="#9C27B0",
                )
            with cg2:
                disp = comm_grp.copy()
                for col in ["avg_price", "min_price", "max_price"]:
                    disp[col] = disp[col].map(lambda x: fmt(x, 2))
                st.dataframe(
                    disp.rename(columns={
                        "commodity": "Commodity", "count": "Materials",
                        "avg_price": "Avg €/kg", "min_price": "Min €/kg", "max_price": "Max €/kg",
                    }),
                    use_container_width=True, hide_index=True,
                )

            # Per-commodity material drill-down
            st.divider()
            sel = st.selectbox("Drill into commodity", sorted(enriched["commodity"].dropna().unique()))
            drill = enriched[enriched["commodity"] == sel][[
                c for c in ["material_id", "supplier", "effective_price", "quote_status", "lead_time_days"]
                if c in enriched.columns
            ]].sort_values("effective_price", ascending=False)
            if "effective_price" in drill.columns:
                drill["effective_price"] = drill["effective_price"].map(lambda x: fmt(x, 2))
            st.dataframe(
                drill.rename(columns={"material_id": "Material", "supplier": "Supplier",
                                      "effective_price": "Price €/kg", "quote_status": "Status",
                                      "lead_time_days": "Lead time (d)"}),
                use_container_width=True, hide_index=True,
            )

    # ── Quote coverage ────────────────────────────────────────────────────────
    with tab_coverage:
        st.subheader("Quote coverage per material")
        if quotes.empty:
            st.info("No quotes loaded.")
        else:
            cov = mats[["material_id"]].copy()
            all_q = quotes.copy()
            if "valid_until" in all_q.columns:
                all_q["valid_until"] = pd.to_datetime(all_q["valid_until"], errors="coerce")
            mat_quotes = all_q.groupby("material_id").agg(
                n_quotes=("material_id", "count"),
                best_price=("price_eur_per_kg", "min") if "price_eur_per_kg" in all_q.columns else ("material_id", "count"),
                n_suppliers=("supplier", "nunique") if "supplier" in all_q.columns else ("material_id", "count"),
            ).reset_index()
            cov = cov.merge(mat_quotes, on="material_id", how="left")
            cov["n_quotes"]    = cov["n_quotes"].fillna(0).astype(int)
            cov["n_suppliers"] = cov.get("n_suppliers", pd.Series([0]*len(cov))).fillna(0).astype(int)

            cov_pct = (cov["n_quotes"] > 0).mean() * 100
            st.metric("Coverage", f"{(cov['n_quotes'] > 0).sum()} / {len(cov)} materials ({cov_pct:.0f}%)")

            if "best_price" in cov.columns:
                cov["best_price"] = cov["best_price"].map(lambda x: fmt(x, 2) if pd.notna(x) else "—")
            cov["Status"] = cov["n_quotes"].apply(
                lambda n: "🟢 Quoted" if n >= 2 else ("🟡 Single quote" if n == 1 else "🔴 No quote")
            )
            st.dataframe(
                cov.rename(columns={
                    "material_id": "Material", "n_quotes": "# Quotes",
                    "n_suppliers": "# Suppliers", "best_price": "Best €/kg",
                }),
                use_container_width=True, hide_index=True,
            )


guard(main)
