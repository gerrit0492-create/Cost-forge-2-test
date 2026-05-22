"""
Quarterly Quote Register — Waterjet size × vendor price tracker.

Products
────────
Waterjet units   — sizes in mm : 510 570 640 720 810 900 1000 1100 1200
                                  1300 1400 1500 1640 1720 1880
Thrust Block Seal— sizes in kN : 129 199 447 720 1600

Vendor codes
────────────
IN01  India-sourced supply
NL07  EI (Netherlands) supply

Update cadence
──────────────
Prices are refreshed every quarter.  The dashboard flags any product/vendor
combination that has not been updated for ≥ 2 quarters.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date

from utils.currency import fmt
from utils.io import load_quarterly_quotes, save_sheet, df_to_excel_bytes
from utils.nav import home_button
from utils.style import inject_css, page_header

st.set_page_config(page_title="Quarterly Quote Register", layout="wide", page_icon="📅")
inject_css()
home_button()
page_header(
    title="Quarterly Quote Register",
    icon="📅",
    caption="IN01 (India) · NL07 (EI/Netherlands) — price by waterjet size & Thrust Block Seal rating",
)

# ── Constants ──────────────────────────────────────────────────────────────────
VENDOR_CODES  = ["IN01", "NL07"]
VENDOR_LABELS = {"IN01": "🇮🇳 IN01 — India", "NL07": "🇳🇱 NL07 — EI / Netherlands"}

JET_SIZES_MM  = [510, 570, 640, 720, 810, 900, 1000, 1100, 1200,
                 1300, 1400, 1500, 1640, 1720, 1880]
TBS_SIZES_KN  = [129, 199, 447, 720, 1600]

PRODUCT_TYPES = ["Waterjet", "Thrust Block Seal"]

# Quarter helpers
def _current_quarter() -> str:
    today = date.today()
    q = (today.month - 1) // 3 + 1
    return f"Q{q}-{today.year}"

def _quarter_list(n: int = 8) -> list[str]:
    """Last n quarters including current."""
    today = date.today()
    quarters = []
    y, q = today.year, (today.month - 1) // 3 + 1
    for _ in range(n):
        quarters.append(f"Q{q}-{y}")
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return quarters  # most-recent first

def _quarter_age(q_str: str) -> int:
    """How many quarters ago is q_str from today? 0 = current quarter."""
    if not q_str or not isinstance(q_str, str):
        return 99
    try:
        qn, yr = q_str.split("-")
        q = int(qn[1:])
        y = int(yr)
        today = date.today()
        cq = (today.month - 1) // 3 + 1
        cy = today.year
        return (cy - y) * 4 + (cq - q)
    except Exception:
        return 99

QUARTER_OPTS = _quarter_list(12)
CUR_QUARTER  = _current_quarter()

STATUS_ICON = {0: "🟢", 1: "🟡", 2: "🟠"}   # quarters since update

# ── Build the full product catalogue skeleton ──────────────────────────────────
def _catalogue() -> pd.DataFrame:
    rows = []
    for v in VENDOR_CODES:
        for s in JET_SIZES_MM:
            rows.append({"vendor_code": v, "product_type": "Waterjet",
                         "size_value": float(s), "size_unit": "mm"})
        for s in TBS_SIZES_KN:
            rows.append({"vendor_code": v, "product_type": "Thrust Block Seal",
                         "size_value": float(s), "size_unit": "kN"})
    return pd.DataFrame(rows)

@st.cache_data(ttl=30)
def _load() -> pd.DataFrame:
    return load_quarterly_quotes()

if st.button("🔄 Refresh", help="Clear cache and reload"):
    st.cache_data.clear()
    st.rerun()

saved = _load()

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.subheader("Filters")
sel_vendors  = st.sidebar.multiselect("Vendor", VENDOR_CODES,
                                       default=VENDOR_CODES,
                                       format_func=lambda v: VENDOR_LABELS[v])
sel_products = st.sidebar.multiselect("Product type", PRODUCT_TYPES, default=PRODUCT_TYPES)
sel_quarter  = st.sidebar.selectbox("Active quarter", QUARTER_OPTS,
                                     index=0, help="Quarter shown in dashboard and editor")
st.sidebar.divider()
st.sidebar.info(
    "**IN01** = India-sourced supply\n\n"
    "**NL07** = EI / Netherlands supply\n\n"
    "Prices updated **quarterly** — 🔴 = overdue (≥2 quarters old)."
)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_dash, tab_enter, tab_compare, tab_history, tab_dl = st.tabs([
    "📊 Dashboard",
    "✏️ Enter / edit prices",
    "⚖️ IN01 vs NL07 comparison",
    "📈 3-quarter history",
    "⬇️ Download",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.subheader(f"Price dashboard — {sel_quarter}")

    cat = _catalogue()
    cat = cat[cat["vendor_code"].isin(sel_vendors) &
              cat["product_type"].isin(sel_products)].copy()

    if saved.empty:
        st.info("No prices entered yet. Go to **Enter / edit prices** to add quarterly quotes.")
    else:
        # Attach latest saved quote for each product/vendor (any quarter, not just sel)
        latest = (
            saved
            .assign(_age=saved["quarter"].map(_quarter_age))
            .sort_values("_age")
            .drop_duplicates(subset=["vendor_code", "product_type", "size_value"])
            .drop(columns=["_age"])
        )
        merged = cat.merge(
            latest[["vendor_code", "product_type", "size_value",
                    "unit_price_eur", "qty", "quarter", "lead_time_days", "notes"]],
            on=["vendor_code", "product_type", "size_value"],
            how="left",
        )
        merged["_age"]      = merged["quarter"].map(_quarter_age)
        merged["Status"]    = merged["_age"].map(
            lambda a: ("🟢 Current"    if pd.notna(a) and a == 0 else
                       ("🟡 1 qtr old" if pd.notna(a) and a == 1 else
                        ("🔴 Overdue"   if pd.notna(a) and a >= 2 else "⚪ No quote")))
        )

        # KPIs
        n_total   = len(merged)
        n_current = int((merged["_age"] == 0).sum())
        n_old1    = int((merged["_age"] == 1).sum())
        n_overdue = int((merged["_age"] >= 2).sum())
        n_missing = int(merged["unit_price_eur"].isna().sum())

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total product/vendor lines", n_total)
        k2.metric("🟢 Current quarter", n_current)
        k3.metric("🟡 1 quarter old",   n_old1)
        k4.metric("🔴 Overdue (≥2 qtrs)", n_overdue,
                  delta="update needed" if n_overdue else None,
                  delta_color="inverse" if n_overdue else "off")
        k5.metric("⚪ No quote yet",    n_missing)

        st.divider()

        # Waterjet table
        for pt in sel_products:
            sub = merged[merged["product_type"] == pt].copy()
            if sub.empty:
                continue
            unit = sub["size_unit"].iloc[0]
            st.subheader(f"{pt} prices ({unit})")

            disp = sub[[
                "vendor_code", "size_value", "qty",
                "unit_price_eur", "quarter", "Status", "lead_time_days", "notes",
            ]].copy()
            disp["vendor_code"]    = disp["vendor_code"].map(VENDOR_LABELS)
            disp[f"Size ({unit})"] = disp["size_value"].map(lambda x: f"{x:g}")
            disp["Qty"]            = disp["qty"].map(lambda x: f"{x:g}" if pd.notna(x) else "—")
            disp["Price (€/unit)"] = disp["unit_price_eur"].map(
                lambda x: fmt(x, 0) if pd.notna(x) else "—")
            disp["Quarter"]        = disp["quarter"].fillna("—")
            disp["Lead (days)"]    = disp["lead_time_days"].map(
                lambda x: f"{x:g}" if pd.notna(x) else "—")
            disp["Notes"]          = disp["notes"].fillna("")

            st.dataframe(
                disp[[f"Size ({unit})", "vendor_code", "Qty",
                      "Price (€/unit)", "Quarter", "Status", "Lead (days)", "Notes"]]
                .rename(columns={"vendor_code": "Vendor"}),
                use_container_width=True, hide_index=True,
            )
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ENTER / EDIT PRICES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_enter:
    st.subheader(f"Enter prices — {sel_quarter}")
    st.caption(
        "One row per vendor × product × size. "
        "Set **Qty** = number of units quoted. "
        "**Price (€/unit)** is the EUR price — fill **Orig currency** + "
        "**Price (orig)** if the quote is in INR/USD and you want to track the source figure."
    )

    cat2 = _catalogue()
    cat2 = cat2[cat2["vendor_code"].isin(sel_vendors) &
                cat2["product_type"].isin(sel_products)].copy()

    # Pull any existing rows for the selected quarter
    existing = pd.DataFrame()
    if not saved.empty:
        existing = saved[
            (saved["quarter"] == sel_quarter) &
            (saved["vendor_code"].isin(sel_vendors)) &
            (saved["product_type"].isin(sel_products))
        ].copy()

    # Merge catalogue with existing to pre-fill editor
    if not existing.empty:
        editor_df = cat2.merge(
            existing[["vendor_code", "product_type", "size_value",
                       "qty", "unit_price_eur", "currency_orig",
                       "price_orig", "lead_time_days", "notes"]],
            on=["vendor_code", "product_type", "size_value"],
            how="left",
        )
    else:
        editor_df = cat2.copy()
        for c in ["qty", "unit_price_eur", "currency_orig", "price_orig",
                  "lead_time_days", "notes"]:
            editor_df[c] = None if c in ["qty","unit_price_eur","price_orig","lead_time_days"] else ""

    editor_df["size_label"] = (
        editor_df["size_value"].map(lambda x: f"{x:g}")
        + " " + editor_df["size_unit"]
    )
    editor_df["vendor_label"] = editor_df["vendor_code"].map(VENDOR_LABELS)

    edited = st.data_editor(
        editor_df,
        column_config={
            "vendor_label":   st.column_config.TextColumn("Vendor",      disabled=True, width="medium"),
            "product_type":   st.column_config.TextColumn("Product",     disabled=True, width="medium"),
            "size_label":     st.column_config.TextColumn("Size",        disabled=True, width="small"),
            "vendor_code":    None,
            "size_value":     None,
            "size_unit":      None,
            "qty":            st.column_config.NumberColumn("Qty", min_value=0, format="%g"),
            "unit_price_eur": st.column_config.NumberColumn("Price (€/unit)", format="%.2f"),
            "currency_orig":  st.column_config.SelectboxColumn(
                                  "Orig currency",
                                  options=["EUR","INR","USD","GBP","JPY"], width="small"),
            "price_orig":     st.column_config.NumberColumn("Price (orig)", format="%.2f"),
            "lead_time_days": st.column_config.NumberColumn("Lead days", format="%g", width="small"),
            "notes":          st.column_config.TextColumn("Notes"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="qq_editor",
    )

    if st.button("💾 Save to workbook", type="primary"):
        # Build rows to save
        new_rows = edited.copy()
        new_rows["quarter"]    = sel_quarter
        new_rows["quote_date"] = date.today().isoformat()
        save_cols = [c for c in [
            "vendor_code", "product_type", "size_value", "size_unit",
            "qty", "unit_price_eur", "currency_orig", "price_orig",
            "quarter", "quote_date", "lead_time_days", "notes",
        ] if c in new_rows.columns]

        # Remove old rows for this quarter+vendor+product combo, append new ones
        if not saved.empty:
            keep = saved[~(
                (saved["quarter"] == sel_quarter) &
                (saved["vendor_code"].isin(sel_vendors)) &
                (saved["product_type"].isin(sel_products))
            )].copy()
            combined = pd.concat([keep, new_rows[save_cols]], ignore_index=True)
        else:
            combined = new_rows[save_cols].copy()

        # Only save rows with a price or qty entered
        combined = combined[
            combined["unit_price_eur"].notna() | combined["qty"].notna()
        ]
        save_sheet(combined, "quarterly_quotes")
        st.success(f"Saved {len(combined)} quote lines for {sel_quarter}.")
        st.cache_data.clear()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IN01 vs NL07 COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("IN01 vs NL07 — side-by-side price comparison")
    st.caption("Shows the most recent quote for each size, regardless of quarter.")

    if saved.empty:
        st.info("No prices saved yet.")
    else:
        latest_all = (
            saved
            .assign(_age=saved["quarter"].map(_quarter_age))
            .sort_values("_age")
            .drop_duplicates(subset=["vendor_code", "product_type", "size_value"])
        )

        for pt in PRODUCT_TYPES:
            sub = latest_all[latest_all["product_type"] == pt].copy()
            if sub.empty:
                continue
            unit = "mm" if pt == "Waterjet" else "kN"
            sizes = JET_SIZES_MM if pt == "Waterjet" else TBS_SIZES_KN

            in01 = (sub[sub["vendor_code"] == "IN01"]
                    .set_index("size_value")[["unit_price_eur", "qty", "quarter"]]
                    .rename(columns={"unit_price_eur": "IN01 price",
                                     "qty": "IN01 qty",
                                     "quarter": "IN01 quarter"}))
            nl07 = (sub[sub["vendor_code"] == "NL07"]
                    .set_index("size_value")[["unit_price_eur", "qty", "quarter"]]
                    .rename(columns={"unit_price_eur": "NL07 price",
                                     "qty": "NL07 qty",
                                     "quarter": "NL07 quarter"}))

            cmp = pd.DataFrame({"size": [float(s) for s in sizes]}).set_index("size")
            cmp = cmp.join(in01).join(nl07)
            cmp.index.name = f"Size ({unit})"
            cmp.index = cmp.index.map(lambda x: f"{x:g}")

            cmp["Δ price"] = cmp["NL07 price"] - cmp["IN01 price"]
            cmp["Δ %"]     = (cmp["Δ price"] / cmp["IN01 price"] * 100).round(1)

            st.markdown(f"### {pt}")
            fmt_cmp = cmp.copy()
            for col in ["IN01 price", "NL07 price", "Δ price"]:
                if col in fmt_cmp.columns:
                    fmt_cmp[col] = fmt_cmp[col].map(
                        lambda x: fmt(x, 0) if pd.notna(x) else "—")
            fmt_cmp["IN01 qty"]  = fmt_cmp["IN01 qty"].map(
                lambda x: f"{x:g}" if pd.notna(x) else "—")
            fmt_cmp["NL07 qty"]  = fmt_cmp["NL07 qty"].map(
                lambda x: f"{x:g}" if pd.notna(x) else "—")
            fmt_cmp["Δ %"]       = fmt_cmp["Δ %"].map(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
            fmt_cmp["IN01 quarter"] = fmt_cmp["IN01 quarter"].fillna("—")
            fmt_cmp["NL07 quarter"] = fmt_cmp["NL07 quarter"].fillna("—")

            st.dataframe(fmt_cmp.reset_index(), use_container_width=True, hide_index=True)

            # Bar chart for sizes with both prices
            chart_data = cmp[["IN01 price", "NL07 price"]].dropna()
            if not chart_data.empty:
                st.bar_chart(chart_data, color=["#FF9900", "#1565C0"])
            st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 3-QUARTER HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("3-quarter price history")
    st.caption("Shows last 3 quarters' prices for each vendor × size combination.")

    if saved.empty:
        st.info("No history yet — enter prices for at least two quarters.")
    else:
        last3 = QUARTER_OPTS[:3]   # current + 2 previous quarters

        hist = saved[saved["quarter"].isin(last3)].copy()
        if hist.empty:
            st.info("No data for the last 3 quarters. Enter prices in the editor.")
        else:
            for pt in PRODUCT_TYPES:
                sub = hist[hist["product_type"] == pt].copy()
                if sub.empty:
                    continue
                unit = "mm" if pt == "Waterjet" else "kN"
                st.markdown(f"### {pt} ({unit})")

                for vendor in VENDOR_CODES:
                    vsub = sub[sub["vendor_code"] == vendor].copy()
                    if vsub.empty:
                        continue
                    pivot = vsub.pivot_table(
                        index="size_value", columns="quarter",
                        values="unit_price_eur", aggfunc="last",
                    )
                    # Keep only last3 columns that exist
                    pivot = pivot[[c for c in last3 if c in pivot.columns]]
                    pivot.index = pivot.index.map(lambda x: f"{x:g} {unit}")
                    pivot.index.name = "Size"

                    # Trend: current vs 1 quarter ago
                    if len(pivot.columns) >= 2:
                        c_now = pivot.columns[0]
                        c_prev = pivot.columns[1]
                        pivot["Trend"] = (pivot[c_now] - pivot[c_prev]).map(
                            lambda x: (f"▲ {fmt(x,0)}" if pd.notna(x) and x > 0
                                       else (f"▼ {fmt(abs(x),0)}" if pd.notna(x) and x < 0
                                             else ("→ unchanged" if pd.notna(x) else "—"))))

                    for col in [c for c in pivot.columns if c.startswith("Q")]:
                        pivot[col] = pivot[col].map(
                            lambda x: fmt(x, 0) if pd.notna(x) else "—")

                    st.markdown(f"**{VENDOR_LABELS[vendor]}**")
                    st.dataframe(pivot.reset_index(), use_container_width=True, hide_index=True)
                st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dl:
    st.subheader("Downloads")

    dl1, dl2 = st.columns(2)

    with dl1:
        st.markdown("**Full register (all quarters)**")
        if not saved.empty:
            st.download_button(
                "⬇️ quarterly_quotes_all.xlsx",
                data=df_to_excel_bytes(saved, "QuarterlyQuotes"),
                file_name="quarterly_quotes_all.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.info("No data yet.")

    with dl2:
        st.markdown("**Blank entry template**")
        tmpl = _catalogue()
        tmpl["quarter"]       = CUR_QUARTER
        tmpl["qty"]           = ""
        tmpl["unit_price_eur"]= ""
        tmpl["currency_orig"] = "EUR"
        tmpl["price_orig"]    = ""
        tmpl["lead_time_days"]= ""
        tmpl["notes"]         = ""
        st.download_button(
            "⬇️ quarterly_quotes_template.xlsx",
            data=df_to_excel_bytes(tmpl, "Template"),
            file_name=f"quarterly_quotes_template_{CUR_QUARTER}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
