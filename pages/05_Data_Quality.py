from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.safe import guard
from utils.validators import all_rules_ok, business_rules, check_missing, check_positive


def _health(ok: bool) -> str:
    return "🟢" if ok else "🔴"


def main() -> None:
    st.set_page_config(page_title="Data Quality", layout="wide", page_icon="✅")
    home_button()
    st.title("✅ Data Quality")
    st.caption("Health check across BOM, materials, processes and supplier quotes — with actionable fix guidance.")

    _, btn = st.columns([6, 1])
    if btn.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    mats   = load_materials()
    procs  = load_processes()
    bom    = load_bom()
    quotes = load_quotes()

    today = pd.Timestamp.today().normalize()

    # ── Pre-compute all checks ─────────────────────────────────────────────────
    # Materials
    m_miss  = check_missing(mats,  ["material_id", "price_eur_per_kg"])
    m_pos   = check_positive(mats, ["price_eur_per_kg"])
    m_no_comm = (mats["commodity"].isna().sum() if "commodity" in mats.columns else 0)

    # Processes
    p_miss  = check_missing(procs, ["process_id", "machine_rate_eur_h",
                                    "labor_rate_eur_h", "overhead_pct", "margin_pct"])
    p_pos   = check_positive(procs, ["machine_rate_eur_h", "labor_rate_eur_h"])

    # BOM
    b_miss  = check_missing(bom, ["line_id", "material_id", "qty",
                                   "mass_kg", "process_route", "runtime_h"])
    b_pos   = check_positive(bom, ["qty", "mass_kg"])
    b_no_route = (
        bom[~bom["process_route"].isin(procs["process_id"])]["line_id"].tolist()
        if "process_route" in bom.columns and "process_id" in procs.columns else []
    )
    b_no_mat = (
        bom[~bom["material_id"].isin(mats["material_id"])]["line_id"].tolist()
        if "material_id" in bom.columns else []
    )

    # Quotes
    q_expired = []
    q_expiring = []
    q_no_cover = []
    if not quotes.empty:
        if "valid_until" in quotes.columns:
            vd = pd.to_datetime(quotes["valid_until"], errors="coerce")
            q_expired  = quotes[vd < today]["material_id"].unique().tolist()
            q_expiring = quotes[vd.between(today, today + pd.Timedelta(days=30))]["material_id"].unique().tolist()
        quoted_ids  = set(quotes["material_id"].unique())
        mat_ids     = set(mats["material_id"].unique()) if not mats.empty else set()
        q_no_cover  = sorted(mat_ids - quoted_ids)

    # Business rules
    rules    = business_rules(mats, procs, bom)
    rules_ok = all_rules_ok(rules)

    # Overall score
    checks = [
        not m_miss, not m_pos, not p_miss, not p_pos,
        not b_miss, not b_pos, not b_no_route, not b_no_mat,
        not q_expired, rules_ok,
    ]
    score = sum(checks)
    total = len(checks)
    pct   = score / total * 100

    # ── Summary header ────────────────────────────────────────────────────────
    bar_colour = "green" if pct == 100 else ("orange" if pct >= 70 else "red")
    status_icon = "✅" if pct == 100 else ("⚠️" if pct >= 70 else "🚨")
    st.subheader(f"{status_icon} Overall health: {score}/{total} checks passed ({pct:.0f}%)")
    st.progress(pct / 100)

    if pct == 100:
        st.success("All data quality checks passed — safe to calculate costs and issue quotes.")
    elif pct >= 70:
        st.warning("Minor issues detected — review before issuing a firm quotation.")
    else:
        st.error("Significant data quality issues — costs may be incomplete or unreliable.")

    st.divider()

    # ── Four domain tabs ──────────────────────────────────────────────────────
    tab_mat, tab_bom, tab_proc, tab_quotes_tab = st.tabs([
        f"{_health(not m_miss and not m_pos)} Materials",
        f"{_health(not b_miss and not b_pos and not b_no_route and not b_no_mat)} BOM",
        f"{_health(not p_miss and not p_pos)} Processes",
        f"{_health(not q_expired)} Quotes",
    ])

    # ── Materials ─────────────────────────────────────────────────────────────
    with tab_mat:
        st.subheader("Material library checks")
        r1, r2, r3 = st.columns(3)
        r1.metric("Total materials", len(mats))
        r2.metric("Missing required fields", len(m_miss),
                  delta="fix needed" if m_miss else "ok",
                  delta_color="inverse" if m_miss else "off")
        r3.metric("Zero / negative prices", len(m_pos),
                  delta="fix needed" if m_pos else "ok",
                  delta_color="inverse" if m_pos else "off")

        if m_miss:
            st.error(f"**Missing fields** in materials: `{', '.join(m_miss)}`  \n"
                     "Fix: open `data/cost_forge.xlsx → Materials` and fill in all highlighted cells.")
        else:
            st.success("✅ All required material fields are present.")

        if m_pos:
            st.error(f"**Zero or negative prices** found: `{', '.join(m_pos)}`  \n"
                     "Fix: update material prices in **Materials** or **Supplier Quotes**.")
        else:
            st.success("✅ All material prices are positive.")

        if m_no_comm:
            st.warning(f"⚠️ **{m_no_comm} material(s)** have no commodity group — "
                       "Scenario Planner commodity sliders won't apply to them.")
        else:
            st.success("✅ All materials have a commodity group assigned.")

        if not mats.empty and "price_eur_per_kg" in mats.columns:
            st.divider()
            st.subheader("Price distribution")
            st.bar_chart(
                mats.set_index("material_id")[["price_eur_per_kg"]].rename(
                    columns={"price_eur_per_kg": "Price €/kg"}
                ).sort_values("Price €/kg", ascending=False),
                color="#2196F3",
            )

    # ── BOM ───────────────────────────────────────────────────────────────────
    with tab_bom:
        st.subheader("BOM checks")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("BOM lines",            len(bom))
        r2.metric("Missing required fields", len(b_miss),
                  delta="fix needed" if b_miss else "ok",
                  delta_color="inverse" if b_miss else "off")
        r3.metric("Unmatched process routes", len(b_no_route),
                  delta="fix needed" if b_no_route else "ok",
                  delta_color="inverse" if b_no_route else "off")
        r4.metric("Unmatched materials",      len(b_no_mat),
                  delta="fix needed" if b_no_mat else "ok",
                  delta_color="inverse" if b_no_mat else "off")

        if b_miss:
            st.error(f"**Missing BOM fields**: `{', '.join(b_miss)}`  \n"
                     "Fix: re-upload BOM via **BOM Import** with all required columns filled.")
        else:
            st.success("✅ All required BOM fields are present.")

        if b_pos:
            st.warning(f"**Zero or negative qty/mass** in BOM: `{', '.join(b_pos)}`")
        else:
            st.success("✅ All BOM quantities and masses are positive.")

        if b_no_route:
            st.error(f"**{len(b_no_route)} BOM line(s)** reference a process route not in the Processes table:  \n"
                     f"`{', '.join(str(x) for x in b_no_route[:10])}{'…' if len(b_no_route) > 10 else ''}`  \n"
                     "Fix: add the missing process route in **Presets** / `cost_forge.xlsx → Processes`.")
        else:
            st.success("✅ All BOM process routes are matched in the Processes table.")

        if b_no_mat:
            st.error(f"**{len(b_no_mat)} BOM line(s)** reference a material not in the Materials table:  \n"
                     f"`{', '.join(str(x) for x in b_no_mat[:10])}{'…' if len(b_no_mat) > 10 else ''}`  \n"
                     "Fix: add the missing material in `cost_forge.xlsx → Materials`.")
        else:
            st.success("✅ All BOM material IDs are matched in the Materials table.")

        if not bom.empty and "mass_kg" in bom.columns:
            st.divider()
            st.subheader("Mass distribution across BOM lines")
            st.bar_chart(
                bom.set_index("line_id")[["mass_kg"]].sort_values("mass_kg", ascending=False).head(30),
                color="#FF9800",
            )

    # ── Processes ─────────────────────────────────────────────────────────────
    with tab_proc:
        st.subheader("Process route checks")
        r1, r2 = st.columns(2)
        r1.metric("Process routes",         len(procs))
        r2.metric("Missing required fields", len(p_miss),
                  delta="fix needed" if p_miss else "ok",
                  delta_color="inverse" if p_miss else "off")

        if p_miss:
            st.error(f"**Missing process fields**: `{', '.join(p_miss)}`  \n"
                     "Fix: open `cost_forge.xlsx → Processes` and fill in all required columns.")
        else:
            st.success("✅ All required process fields are present.")

        if p_pos:
            st.error(f"**Zero or negative rates** in processes: `{', '.join(p_pos)}`  \n"
                     "Fix: check machine and labour rates in `cost_forge.xlsx → Processes`.")
        else:
            st.success("✅ All process rates are positive.")

        if not procs.empty:
            st.divider()
            st.subheader("Rate comparison across process routes")
            rate_cols = [c for c in ["machine_rate_eur_h", "labor_rate_eur_h"] if c in procs.columns]
            if rate_cols:
                renamed = procs.set_index("process_id")[rate_cols].rename(
                    columns={"machine_rate_eur_h": "Machine €/h", "labor_rate_eur_h": "Labour €/h"}
                )
                sort_col = "Machine €/h" if "machine_rate_eur_h" in rate_cols else renamed.columns[0]
                st.dataframe(
                    renamed.sort_values(sort_col, ascending=False),
                    use_container_width=True,
                )

    # ── Quotes ────────────────────────────────────────────────────────────────
    with tab_quotes_tab:
        st.subheader("Supplier quote checks")

        if quotes.empty:
            st.info("No quotes loaded — import via **CSV Import** or add to `cost_forge.xlsx → Quotes`.")
        else:
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Total quote lines",    len(quotes))
            r2.metric("Expired",              len(q_expired),
                      delta="action needed" if q_expired else "all valid",
                      delta_color="inverse" if q_expired else "off")
            r3.metric("Expiring ≤30 days",   len(q_expiring),
                      delta="renew soon" if q_expiring else "ok",
                      delta_color="inverse" if q_expiring else "off")
            r4.metric("Materials not quoted", len(q_no_cover),
                      delta="add quotes" if q_no_cover else "fully covered",
                      delta_color="inverse" if q_no_cover else "off")

            if q_expired:
                st.error(
                    f"**{len(q_expired)} material(s) with expired quotes:** "
                    f"{', '.join(q_expired)}  \n"
                    "These materials use fallback base price — update in **Supplier Quotes** or **CSV Import**."
                )
            else:
                st.success("✅ No expired supplier quotes.")

            if q_expiring:
                st.warning(
                    f"⚠️ **{len(q_expiring)} material(s)** have quotes expiring within 30 days: "
                    f"{', '.join(q_expiring)}  \nContact suppliers to renew before issuing the next quote."
                )

            if q_no_cover:
                st.warning(
                    f"⚠️ **{len(q_no_cover)} material(s)** have no supplier quote at all: "
                    f"{', '.join(q_no_cover[:10])}{'…' if len(q_no_cover) > 10 else ''}  \n"
                    "Costs use base material price — get quotes to firm up cost accuracy."
                )
            else:
                st.success("✅ All materials have at least one supplier quote.")

        # Business rules summary
        st.divider()
        st.subheader("Business rules")
        if rules_ok:
            st.success("✅ All business rules passed.")
        else:
            st.error("Business rule violations detected:")
            for rule in rules:
                if not rule.ok:
                    st.warning(f"**{rule.name}**: {rule.msg}")


guard(main)
