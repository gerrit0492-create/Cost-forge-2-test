from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.io import load_materials, load_quotes
from utils.nav import home_button
from utils.quotes import best_quotes
from utils.safe import guard


def main() -> None:
    st.set_page_config(page_title="Supplier Quotes", layout="wide", page_icon="🏭")
    home_button()
    st.title("🏭 Procurement Intelligence")
    st.caption("Supplier spend, quote validity, price competitiveness and lead-time risk.")

    # ── Quarterly Quote Register summary strip ─────────────────────────────────
    from utils.io import load_quarterly_quotes as _load_qq
    from datetime import date as _date

    def _qq_age(q_str: str) -> int:
        try:
            qn, yr = str(q_str).split("-")
            q, y = int(qn[1:]), int(yr)
            today = _date.today()
            cq = (today.month - 1) // 3 + 1
            return (today.year - y) * 4 + (cq - q)
        except Exception:
            return 99

    _qq = _load_qq()
    _cur_q = f"Q{(_date.today().month-1)//3+1}-{_date.today().year}"
    if not _qq.empty:
        _latest_qq = (
            _qq.assign(_age=_qq["quarter"].map(_qq_age))
            .sort_values("_age")
            .drop_duplicates(subset=["vendor_code", "product_type", "size_value"])
        )
        _n_in01    = int((_latest_qq["vendor_code"] == "IN01").sum())
        _n_nl07    = int((_latest_qq["vendor_code"] == "NL07").sum())
        _n_overdue = int((_latest_qq["_age"] >= 2).sum())
    else:
        _n_in01 = _n_nl07 = _n_overdue = 0

    with st.container(border=True):
        st.caption("📅 **Quarterly Price Register** — IN01 (India) & NL07 (EI/Netherlands) "
                   "| Jet sizes 510–1880 mm · Thrust Block Seal 129–1600 kN")
        _qa, _qb, _qc, _qd = st.columns(4)
        _qa.metric("IN01 (India) lines", _n_in01 if _n_in01 else "no data")
        _qb.metric("NL07 (EI/NL) lines", _n_nl07 if _n_nl07 else "no data")
        _qc.metric("🔴 Overdue (≥2 qtrs)", _n_overdue,
                   delta="update needed" if _n_overdue else ("no data" if not _n_in01 and not _n_nl07 else "all current"),
                   delta_color="inverse" if _n_overdue else "off")
        _qd.metric("Current quarter", _cur_q)
    st.caption("→ Open **📅 Quarterly Quote Register** in the sidebar to enter / edit prices by size.")
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    quotes = load_quotes()
    mats   = load_materials()

    if quotes.empty:
        st.info("No supplier quotes found. Import quotes via **CSV Import** or edit `data/cost_forge.xlsx`.")
        return

    today = pd.Timestamp.today().normalize()
    q = quotes.copy()
    if "valid_until" in q.columns:
        q["valid_until"] = pd.to_datetime(q["valid_until"], errors="coerce")
        q["expired"]     = q["valid_until"] < today
        q["days_left"]   = (q["valid_until"] - today).dt.days
    else:
        q["expired"]   = False
        q["days_left"] = 9999

    has_lead  = "lead_time_days" in q.columns
    has_supp  = "supplier"       in q.columns
    has_valid = "valid_until"    in q.columns

    # ── KPI strip ─────────────────────────────────────────────────────────────
    n_suppliers   = q["supplier"].nunique() if has_supp else "—"
    n_materials   = q["material_id"].nunique()
    n_total_mats  = len(mats)
    n_expired     = int(q["expired"].sum())
    n_expiring_30 = int((q["days_left"].between(0, 30)).sum()) if has_valid else 0
    max_lt        = int(q["lead_time_days"].max()) if has_lead else 0
    coverage_pct  = n_materials / n_total_mats * 100 if n_total_mats else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Suppliers",         n_suppliers)
    k2.metric("Materials quoted",  f"{n_materials} / {n_total_mats}",
              delta=f"{coverage_pct:.0f}% coverage", delta_color="off")
    k3.metric("Expired quotes",    n_expired,
              delta="action needed" if n_expired else "all valid",
              delta_color="inverse" if n_expired else "off")
    k4.metric("Expiring ≤30 days", n_expiring_30,
              delta="renew soon" if n_expiring_30 else "ok",
              delta_color="inverse" if n_expiring_30 else "off")
    k5.metric("Max lead time",     f"{max_lt} days" if has_lead else "—")
    k6.metric("Coverage gap",      f"{n_total_mats - n_materials} materials",
              delta="no quote" if (n_total_mats - n_materials) else "fully covered",
              delta_color="inverse" if (n_total_mats - n_materials) else "off")

    st.divider()

    tab_status, tab_compare, tab_spend, tab_leadtime, tab_gaps = st.tabs([
        "📋 Quote status",
        "⚖️ Price comparison",
        "💰 Spend & concentration",
        "⏱️ Lead-time risk",
        "❌ Coverage gaps",
    ])

    # ── Quote status ──────────────────────────────────────────────────────────
    with tab_status:
        st.subheader("Quote validity — best price per material")
        best = best_quotes(q)
        status = best.copy()
        if has_valid:
            status["Status"] = status["valid_until"].apply(
                lambda d: ("🔴 Expired" if pd.notna(d) and d < today
                           else ("🟡 Expiring ≤30d" if pd.notna(d) and (d - today).days <= 30
                                 else "🟢 Valid"))
            )
            status["Expires"]   = pd.to_datetime(status["valid_until"]).dt.strftime("%d %b %Y")
            status["Days left"] = (pd.to_datetime(status["valid_until"]) - today).dt.days.astype("Int64")
        if "price_eur_per_kg" in status.columns:
            status["Price €/kg"] = status["price_eur_per_kg"].map(lambda x: fmt(x, 2))

        show_cols = ["material_id"]
        if has_supp:   show_cols.append("supplier")
        show_cols.append("Price €/kg")
        if has_valid:  show_cols += ["Status", "Expires", "Days left"]
        if has_lead:   show_cols.append("lead_time_days")
        st.dataframe(
            status[[c for c in show_cols if c in status.columns]].rename(columns={
                "material_id": "Material", "supplier": "Supplier",
                "lead_time_days": "Lead time (d)",
            }),
            use_container_width=True, hide_index=True,
        )

        if has_valid:
            st.divider()
            st.subheader("Expiry timeline — next 180 days")
            upcoming = q[q["days_left"].between(0, 180)].sort_values("days_left")
            if not upcoming.empty:
                up = upcoming.copy()
                up["Expires"]   = up["valid_until"].dt.strftime("%d %b %Y")
                up["Days left"] = up["days_left"]
                up_cols = ["material_id"]
                if has_supp: up_cols.append("supplier")
                up_cols += ["price_eur_per_kg", "Expires", "Days left"]
                st.dataframe(
                    up[[c for c in up_cols if c in up.columns]].rename(columns={
                        "material_id": "Material", "supplier": "Supplier",
                        "price_eur_per_kg": "Price €/kg",
                    }),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.success("No quotes expiring in the next 180 days.")

    # ── Price comparison ──────────────────────────────────────────────────────
    with tab_compare:
        st.subheader("Price comparison — all suppliers per material")
        mat_list = sorted(q["material_id"].unique().tolist())
        selected = st.selectbox("Select material", mat_list)
        mat_q    = q[q["material_id"] == selected].sort_values("price_eur_per_kg")

        if "price_eur_per_kg" in mat_q.columns and not mat_q.empty:
            best_price = mat_q["price_eur_per_kg"].min()
            cp1, cp2   = st.columns([2, 1])

            with cp2:
                for _, row in mat_q.iterrows():
                    p       = row.get("price_eur_per_kg", 0)
                    sup     = row.get("supplier", "—")
                    is_best = abs(p - best_price) < 0.001
                    is_exp  = bool(row.get("expired", False))
                    badge   = "✅ best price" if is_best else ("🔴 expired" if is_exp else "")
                    with st.container(border=True):
                        st.markdown(f"**{sup}** &nbsp; {badge}")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("€/kg", fmt(p, 2))
                        if has_valid and pd.notna(row.get("valid_until")):
                            c2.metric("Valid until", row["valid_until"].strftime("%d %b %Y"))
                        if has_lead and pd.notna(row.get("lead_time_days")):
                            c3.metric("Lead time", f"{int(row['lead_time_days'])} d")

            with cp1:
                if has_supp and len(mat_q) > 1:
                    chart_df = mat_q.set_index("supplier")[["price_eur_per_kg"]].rename(
                        columns={"price_eur_per_kg": "Price €/kg"}
                    )
                    st.bar_chart(chart_df, color="#2196F3")

            if len(mat_q) > 1:
                spread     = mat_q["price_eur_per_kg"].max() - best_price
                spread_pct = spread / best_price * 100 if best_price else 0
                st.info(f"Price spread: **{fmt(spread, 2)}/kg** ({spread_pct:.1f}%) "
                        f"between cheapest and most expensive supplier.")

    # ── Spend & concentration ─────────────────────────────────────────────────
    with tab_spend:
        st.subheader("Material spend by supplier")
        if not has_supp:
            st.info("No `supplier` column in quote data.")
        else:
            try:
                from utils.io import load_bom, load_processes
                from utils.pricing import compute_costs
                from utils.quotes import apply_best_quotes

                cost_df  = compute_costs(apply_best_quotes(mats, quotes), load_processes(), load_bom())
                best_q   = best_quotes(quotes)
                spend_df = cost_df.merge(best_q[["material_id", "supplier"]], on="material_id", how="left")
                spend_by = (
                    spend_df.groupby("supplier")["material_cost"]
                    .sum().sort_values(ascending=False).reset_index()
                )
                total_spend = spend_by["material_cost"].sum()
                spend_by["Share %"]      = spend_by["material_cost"] / total_spend * 100
                spend_by["Cumulative %"] = spend_by["Share %"].cumsum()

                sp1, sp2 = st.columns([2, 1])
                with sp1:
                    st.bar_chart(
                        spend_by.set_index("supplier")[["material_cost"]].rename(
                            columns={"material_cost": "Material spend (€)"}
                        ), color="#2196F3"
                    )
                with sp2:
                    disp = spend_by.copy()
                    disp["material_cost"] = disp["material_cost"].map(lambda x: fmt(x))
                    disp["Share %"]       = disp["Share %"].map(lambda x: f"{x:.1f}%")
                    disp["Cumulative %"]  = disp["Cumulative %"].map(lambda x: f"{x:.1f}%")
                    st.dataframe(
                        disp.rename(columns={"supplier": "Supplier", "material_cost": "Spend"}),
                        use_container_width=True, hide_index=True,
                    )

                top1_share = spend_by["Share %"].iloc[0] if not spend_by.empty else 0
                if top1_share > 50:
                    st.warning(
                        f"⚠️ **Concentration risk:** {spend_by['supplier'].iloc[0]} represents "
                        f"**{top1_share:.0f}%** of material spend — consider dual-sourcing."
                    )
            except Exception as exc:
                st.info(f"Could not compute spend by supplier: {exc}")

    # ── Lead-time risk ────────────────────────────────────────────────────────
    with tab_leadtime:
        st.subheader("Procurement lead-time risk")
        if not has_lead:
            st.info("Add `lead_time_days` to supplier quotes to enable this analysis.")
        else:
            lt_df = (
                q.groupby("material_id")["lead_time_days"]
                .max().reset_index().sort_values("lead_time_days", ascending=False)
            )
            if has_supp:
                lt_df = lt_df.merge(
                    q.groupby("material_id")["supplier"].first().reset_index(),
                    on="material_id", how="left",
                )
            lt_df["Risk"] = lt_df["lead_time_days"].apply(
                lambda d: "🔴 Critical (>90d)" if d > 90
                          else ("🟠 High (60–90d)" if d >= 60
                                else ("🟡 Medium (30–60d)" if d >= 30 else "🟢 Low (<30d)"))
            )
            crit_count = (lt_df["lead_time_days"] > 90).sum()

            lt1, lt2 = st.columns([2, 1])
            with lt1:
                st.bar_chart(
                    lt_df.set_index("material_id")[["lead_time_days"]].rename(
                        columns={"lead_time_days": "Lead time (days)"}
                    ), color="#FF9800"
                )
            with lt2:
                st.dataframe(
                    lt_df.rename(columns={"material_id": "Material", "supplier": "Supplier",
                                          "lead_time_days": "Lead time (d)"}),
                    use_container_width=True, hide_index=True,
                )
            if crit_count:
                st.error(f"🚨 {crit_count} material(s) with lead time >90 days — order immediately.")

    # ── Coverage gaps ─────────────────────────────────────────────────────────
    with tab_gaps:
        st.subheader("Materials without a valid supplier quote")
        quoted_ids  = set(q[~q["expired"]]["material_id"].unique())
        all_mat_ids = set(mats["material_id"].unique())
        missing_ids = all_mat_ids - quoted_ids

        if not missing_ids:
            st.success("✅ Every material has at least one valid supplier quote.")
        else:
            st.warning(f"⚠️ **{len(missing_ids)} material(s)** have no valid quote — "
                       "costs use the base material price, not a confirmed supplier price.")
            gap_cols = [c for c in ["material_id", "commodity", "price_eur_per_kg"] if c in mats.columns]
            gap_df   = mats[mats["material_id"].isin(missing_ids)][gap_cols].rename(columns={
                "material_id": "Material", "commodity": "Commodity",
                "price_eur_per_kg": "Base price €/kg",
            })
            if "Base price €/kg" in gap_df.columns:
                gap_df["Base price €/kg"] = gap_df["Base price €/kg"].map(lambda x: fmt(x, 2))
            st.dataframe(gap_df, use_container_width=True, hide_index=True)


guard(main)
