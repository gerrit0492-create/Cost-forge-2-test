from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.safe import guard
from utils.style import inject_css, page_header
from utils.validators import all_rules_ok, business_rules, check_missing, check_positive, material_lines


def _health(ok: bool) -> str:
    return "🟢" if ok else "🔴"


def main() -> None:
    st.set_page_config(page_title="Data Quality", layout="wide", page_icon="✅")
    inject_css()
    home_button()
    page_header(
        title="Data Quality",
        icon="✅",
        caption="Health check across BOM, materials, processes and supplier quotes — with actionable fix guidance.",
    )

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

    # BOM — qty check on material-based lines only; mass_kg=0 is valid for service ops
    mat_bom = material_lines(bom)
    b_miss  = check_missing(bom, ["line_id", "material_id", "qty",
                                   "mass_kg", "process_route", "runtime_h"])
    b_pos   = check_positive(mat_bom, ["qty"])   # mass_kg=0 allowed (NDT/assembly/service)
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

    # ── New: duplicate & orphan checks ────────────────────────────────────────
    # Duplicate material IDs
    m_dupe_ids = (
        mats[mats.duplicated("material_id", keep=False)]["material_id"].unique().tolist()
        if not mats.empty and "material_id" in mats.columns else []
    )
    # BOM lines referencing a material_id not in Materials (orphaned BOM lines already in b_no_mat)
    # Materials in Materials sheet not referenced anywhere in BOM (unused materials)
    bom_mat_ids  = set(bom["material_id"].dropna().unique()) if "material_id" in bom.columns else set()
    all_mat_ids  = set(mats["material_id"].dropna().unique()) if not mats.empty else set()
    m_unused     = sorted(all_mat_ids - bom_mat_ids)

    # Duplicate BOM line IDs
    b_dupe_ids = (
        bom[bom.duplicated("line_id", keep=False)]["line_id"].unique().tolist()
        if not bom.empty and "line_id" in bom.columns else []
    )
    # Contradictory yield factors (same material_id, different yield_factor on different lines)
    b_yield_conflict = []
    if "yield_factor" in bom.columns and "material_id" in bom.columns:
        yf_by_mat = (
            bom[bom["material_id"].notna()]
            .groupby("material_id")["yield_factor"]
            .nunique()
        )
        b_yield_conflict = yf_by_mat[yf_by_mat > 1].index.tolist()

    # Materials without MOQ or HS code (advisory only)
    m_no_moq = (
        int(mats["moq_kg"].isna().sum()) if "moq_kg" in mats.columns else len(mats)
    )
    m_no_hs  = (
        int(mats["hs_code"].isna().sum() + (mats["hs_code"] == "").sum())
        if "hs_code" in mats.columns else len(mats)
    )

    # Processes without tooling consumable rate (advisory)
    p_no_tooling = (
        int(procs["tooling_consumable_eur_h"].isna().sum())
        if "tooling_consumable_eur_h" in procs.columns else len(procs)
    )

    # Business rules
    rules    = business_rules(mats, procs, bom)
    rules_ok = all_rules_ok(rules)

    # Overall score
    checks = [
        not m_miss, not m_pos, not m_dupe_ids,
        not p_miss, not p_pos,
        not b_miss, not b_pos, not b_no_route, not b_no_mat, not b_dupe_ids,
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

    # ── Five domain tabs ──────────────────────────────────────────────────────
    tab_mat, tab_bom, tab_proc, tab_quotes_tab, tab_adv = st.tabs([
        f"{_health(not m_miss and not m_pos and not m_dupe_ids)} Materials",
        f"{_health(not b_miss and not b_pos and not b_no_route and not b_no_mat and not b_dupe_ids)} BOM",
        f"{_health(not p_miss and not p_pos)} Processes",
        f"{_health(not q_expired)} Quotes",
        "🔍 Advanced",
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

        if m_dupe_ids:
            st.error(
                f"**{len(m_dupe_ids)} duplicate material ID(s):** `{', '.join(str(x) for x in m_dupe_ids)}`  \n"
                "Duplicate IDs cause unpredictable merge behaviour. Remove duplicates from the Materials sheet."
            )
        else:
            st.success("✅ No duplicate material IDs.")

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

        if b_dupe_ids:
            st.error(
                f"**{len(b_dupe_ids)} duplicate BOM line ID(s):** "
                f"`{', '.join(str(x) for x in b_dupe_ids[:10])}`  \n"
                "Duplicate line IDs cause incorrect cost aggregation. Fix in the BOM sheet."
            )
        else:
            st.success("✅ No duplicate BOM line IDs.")

        if b_yield_conflict:
            st.warning(
                f"⚠️ **{len(b_yield_conflict)} material(s)** have inconsistent yield factors across BOM lines: "
                f"`{', '.join(str(x) for x in b_yield_conflict)}`  \n"
                "Different yield factors for the same material suggest a data entry error."
            )
        else:
            st.success("✅ Yield factors are consistent across BOM lines.")

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

    # ── Advanced checks tab ───────────────────────────────────────────────────
    with tab_adv:
        st.subheader("Advanced data checks")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Material library completeness**")
            adv_mat_rows = [
                ("Materials total",          len(mats),       ""),
                ("Without MOQ",              m_no_moq,        "⚠️ MOQ excess risk" if m_no_moq else "✅"),
                ("Without HS tariff code",   m_no_hs,         "⚠️ Duty rate risk" if m_no_hs else "✅"),
                ("Unused (not in BOM)",      len(m_unused),   "ℹ️ Consider removing" if m_unused else "✅"),
                ("Duplicate IDs",            len(m_dupe_ids), "🔴 Fix required" if m_dupe_ids else "✅"),
                ("No commodity group",       m_no_comm,       "⚠️ Scenario Planner gap" if m_no_comm else "✅"),
            ]
            st.dataframe(pd.DataFrame(adv_mat_rows, columns=["Check", "Count", "Status"]),
                         use_container_width=True, hide_index=True)

            if m_unused:
                with st.expander(f"Unused materials ({len(m_unused)})"):
                    st.write(m_unused)

        with col_b:
            st.markdown("**Process route completeness**")
            adv_proc_rows = [
                ("Process routes total",           len(procs),       ""),
                ("Without tooling consumable rate", p_no_tooling,    "⚠️ Cost underestimate" if p_no_tooling else "✅"),
                ("Rework % not set",
                 int(procs["rework_pct"].isna().sum()) if "rework_pct" in procs.columns else len(procs),
                 "⚠️ No rework provision"),
                ("Energy kW not set",
                 int(procs["energy_kw"].isna().sum()) if "energy_kw" in procs.columns else len(procs),
                 "⚠️ Energy cost missing"),
            ]
            st.dataframe(pd.DataFrame(adv_proc_rows, columns=["Check", "Count", "Status"]),
                         use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("BOM consistency checks")
        adv_bom_rows = [
            ("Duplicate BOM line IDs",       len(b_dupe_ids),       "🔴 Fix required" if b_dupe_ids else "✅"),
            ("Yield factor conflicts",        len(b_yield_conflict), "⚠️ Review" if b_yield_conflict else "✅"),
            ("Orphaned material references",  len(b_no_mat),         "🔴 Fix required" if b_no_mat else "✅"),
            ("Orphaned process references",   len(b_no_route),       "🔴 Fix required" if b_no_route else "✅"),
        ]
        st.dataframe(pd.DataFrame(adv_bom_rows, columns=["Check", "Count", "Status"]),
                     use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("What these mean for your quote")
        st.info(
            "**Missing MOQ** → You may purchase excess material on low-quantity lines. "
            "Add `moq_kg` to Materials sheet and check Management Dashboard for excess cost.  \n\n"
            "**Missing HS code** → Import duty calculations in Transport module use your manual duty %, "
            "but wrong HS codes risk customs clearance delays and reclassification.  \n\n"
            "**Missing tooling rate** → Cutting tool consumption for precision machining (NAB, stainless) "
            "is a real cost — typically €15–40/hour. Add to the Processes sheet.  \n\n"
            "**Missing rework %** → Precision parts have a real rework rate (3–5% of process cost). "
            "Without it your process cost is systematically understated."
        )


guard(main)
