from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes, save_sheet
from utils.completeness import WATERJET_SUBSYSTEMS, completeness_score, detect_subsystems, missing_subsystems
from utils.nav import home_button
from utils.project import load_project_meta, save_project_meta
from utils.quotes import expired_quote_materials
from utils.safe import guard
from utils.validators import all_rules_ok, business_rules, check_missing, check_positive

MATURITY_OPTIONS = ["RoM (±30%)", "Budget (±15%)", "Definitive (±5%)", "Firm"]


def _compute_checks():
    mats   = load_materials()
    procs  = load_processes()
    bom    = load_bom()
    quotes = load_quotes()
    today  = pd.Timestamp.today().normalize()

    m_miss   = check_missing(mats,  ["material_id", "price_eur_per_kg"])
    m_pos    = check_positive(mats, ["price_eur_per_kg"])
    p_miss   = check_missing(procs, ["process_id", "machine_rate_eur_h",
                                      "labor_rate_eur_h", "overhead_pct", "margin_pct"])
    p_pos    = check_positive(procs, ["machine_rate_eur_h", "labor_rate_eur_h"])
    b_miss   = check_missing(bom,   ["line_id", "material_id", "qty",
                                      "mass_kg", "process_route", "runtime_h"])
    b_pos    = check_positive(bom,  ["qty", "mass_kg"])
    b_no_rt  = (bom[~bom["process_route"].isin(procs["process_id"])]["line_id"].tolist()
                if "process_route" in bom.columns and "process_id" in procs.columns else [])
    b_no_mat = (bom[~bom["material_id"].isin(mats["material_id"])]["line_id"].tolist()
                if "material_id" in bom.columns else [])

    if "valid_until" in quotes.columns and not quotes.empty:
        vd = pd.to_datetime(quotes["valid_until"], errors="coerce")
        q_expired_ids = quotes[vd < today]["material_id"].unique().tolist()
    else:
        q_expired_ids = []

    rules    = business_rules(mats, procs, bom)
    rules_ok = all_rules_ok(rules)

    dq_checks = [not m_miss, not m_pos, not p_miss, not p_pos,
                 not b_miss, not b_pos, not b_no_rt, not b_no_mat,
                 not q_expired_ids, rules_ok]
    dq_score  = sum(dq_checks)

    quoted_ids  = set()
    if not quotes.empty:
        if "valid_until" in quotes.columns:
            vd2 = pd.to_datetime(quotes["valid_until"], errors="coerce")
            quoted_ids = set(quotes[vd2 >= today]["material_id"].unique())
        else:
            quoted_ids = set(quotes["material_id"].unique())
    unquoted = sorted(set(mats["material_id"].unique()) - quoted_ids) if not mats.empty else []

    zero_rt_lines = []
    if "runtime_h" in bom.columns:
        mask = pd.to_numeric(bom["runtime_h"], errors="coerce").fillna(0) == 0
        zero_rt_lines = bom[mask]["line_id"].tolist()

    zero_mass_lines = []
    if "mass_kg" in bom.columns:
        mask2 = pd.to_numeric(bom["mass_kg"], errors="coerce").fillna(0) <= 0
        zero_mass_lines = bom[mask2]["line_id"].tolist()

    comp_score    = completeness_score(bom)
    missing_subs  = missing_subsystems(bom)
    crit_missing  = [(p, i) for p, i in missing_subs if i["critical"]]

    expired_mats  = expired_quote_materials(quotes)

    return dict(
        mats=mats, procs=procs, bom=bom, quotes=quotes, today=today,
        m_miss=m_miss, m_pos=m_pos, p_miss=p_miss, p_pos=p_pos,
        b_miss=b_miss, b_pos=b_pos, b_no_rt=b_no_rt, b_no_mat=b_no_mat,
        q_expired_ids=q_expired_ids, rules_ok=rules_ok,
        dq_score=dq_score, unquoted=unquoted,
        zero_rt_lines=zero_rt_lines, zero_mass_lines=zero_mass_lines, crit_missing=crit_missing,
        comp_score=comp_score, expired_mats=expired_mats,
    )


def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"


def _section(label: str):
    st.markdown(f"### {label}")


def main() -> None:
    st.set_page_config(page_title="Action Centre", layout="wide", page_icon="🔧")
    home_button()
    st.title("🔧 Action Centre")
    st.caption("Fix all open issues in one place — editable tables save directly to the workbook.")

    if st.button("🔄 Re-check all"):
        st.cache_data.clear()
        st.rerun()

    c = _compute_checks()
    meta    = load_project_meta()
    maturity = meta.get("maturity", "Budget (±15%)")
    today   = c["today"]

    # ── Overall progress ──────────────────────────────────────────────────────
    checks = {
        "Expired quotes resolved":         not c["q_expired_ids"],
        "All materials quoted":             not c["unquoted"],
        "Data Quality ≥ 8/10":             c["dq_score"] >= 8,
        "No zero-runtime BOM lines":        not c["zero_rt_lines"],
        "No zero-mass BOM lines":           not c["zero_mass_lines"],
        "Critical subsystems present":      not c["crit_missing"],
        "BOM fields complete":              not c["b_miss"] and not c["b_no_rt"] and not c["b_no_mat"],
        "Material prices valid":            not c["m_miss"] and not c["m_pos"],
        "Process rates valid":              not c["p_miss"] and not c["p_pos"],
        "Business rules pass":              c["rules_ok"],
        "Estimate maturity ≥ Definitive":   maturity in ("Definitive (±5%)", "Firm"),
    }
    n_done  = sum(checks.values())
    n_total = len(checks)
    pct     = n_done / n_total

    col_prog, col_score = st.columns([5, 1])
    col_prog.progress(pct, text=f"{n_done}/{n_total} action items resolved")
    col_score.metric("Resolved", f"{pct*100:.0f}%")

    if n_done == n_total:
        st.success("✅ All action items resolved — safe to advance estimate maturity.")
        st.divider()

    # ── Checklist summary ─────────────────────────────────────────────────────
    with st.expander("📋 Full checklist", expanded=False):
        for label, ok in checks.items():
            st.markdown(f"{'✅' if ok else '❌'} {label}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 1 — EXPIRED QUOTES
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(not c['q_expired_ids'])} Fix expired supplier quotes")

    if not c["q_expired_ids"]:
        st.success("No expired quotes — nothing to fix here.")
    else:
        st.warning(
            f"{len(c['q_expired_ids'])} material(s) have expired quotes: "
            f"{', '.join(c['q_expired_ids'][:8])}{'…' if len(c['q_expired_ids']) > 8 else ''}"
        )
        st.markdown(
            "Edit the table below — update **Price €/kg** and set a new **valid_until** date "
            "(format: YYYY-MM-DD). Then click **Save updated quotes**."
        )
        q = c["quotes"].copy()
        if "valid_until" in q.columns:
            vd = pd.to_datetime(q["valid_until"], errors="coerce")
            expired_rows = q[vd < today].copy()
        else:
            expired_rows = q[q["material_id"].isin(c["q_expired_ids"])].copy()

        edit_cols = [col for col in ["material_id", "supplier", "price_eur_per_kg",
                                     "valid_until", "lead_time_days"] if col in expired_rows.columns]
        edited = st.data_editor(
            expired_rows[edit_cols].reset_index(drop=True),
            column_config={
                "material_id":      st.column_config.TextColumn("Material", disabled=True),
                "supplier":         st.column_config.TextColumn("Supplier"),
                "price_eur_per_kg": st.column_config.NumberColumn("Price €/kg", min_value=0.0, format="%.4f"),
                "valid_until":      st.column_config.TextColumn("Valid until (YYYY-MM-DD)"),
                "lead_time_days":   st.column_config.NumberColumn("Lead time (d)", min_value=0),
            },
            use_container_width=True, num_rows="fixed", key="fix_expired",
        )
        if st.button("💾 Save updated quotes", key="save_expired"):
            updated_q = q.copy()
            updated_q = updated_q[~updated_q.index.isin(expired_rows.index)]
            updated_q = pd.concat([updated_q, edited], ignore_index=True)
            save_sheet(updated_q, "quotes")
            st.cache_data.clear()
            st.success("Saved — click 🔄 Re-check all to verify.")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 2 — ADD MISSING QUOTES
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(not c['unquoted'])} Add supplier quotes for unquoted materials")

    if not c["unquoted"]:
        st.success("All materials have at least one valid quote.")
    else:
        st.warning(
            f"{len(c['unquoted'])} material(s) have no valid supplier quote — "
            "these use the base catalogue price."
        )
        st.markdown(
            "Fill in **Supplier**, **Price €/kg** and **Valid until** for each material. "
            "Leave a row blank to skip it. Then click **Save new quotes**."
        )
        template = pd.DataFrame({
            "material_id":      c["unquoted"],
            "supplier":         [""] * len(c["unquoted"]),
            "price_eur_per_kg": [None] * len(c["unquoted"]),
            "valid_until":      [""] * len(c["unquoted"]),
            "lead_time_days":   [None] * len(c["unquoted"]),
        })
        new_quotes = st.data_editor(
            template,
            column_config={
                "material_id":      st.column_config.TextColumn("Material", disabled=True),
                "supplier":         st.column_config.TextColumn("Supplier"),
                "price_eur_per_kg": st.column_config.NumberColumn("Price €/kg", min_value=0.0, format="%.4f"),
                "valid_until":      st.column_config.TextColumn("Valid until (YYYY-MM-DD)"),
                "lead_time_days":   st.column_config.NumberColumn("Lead time (d)", min_value=0),
            },
            use_container_width=True, num_rows="fixed", key="fix_unquoted",
        )
        if st.button("💾 Save new quotes", key="save_unquoted"):
            to_add = new_quotes[new_quotes["price_eur_per_kg"].notna() &
                                (new_quotes["supplier"].str.strip() != "")]
            if to_add.empty:
                st.warning("No rows filled in — nothing saved.")
            else:
                updated_q = pd.concat([c["quotes"], to_add], ignore_index=True)
                save_sheet(updated_q, "quotes")
                st.cache_data.clear()
                st.success(f"Saved {len(to_add)} quote(s) — click 🔄 Re-check all.")
                st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 3 — ZERO RUNTIME LINES
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(not c['zero_rt_lines'])} Fix BOM lines with zero process runtime")

    if not c["zero_rt_lines"]:
        st.success("All BOM lines have a non-zero runtime_h value.")
    else:
        st.warning(
            f"{len(c['zero_rt_lines'])} BOM line(s) have runtime_h = 0 — "
            "process cost for these lines is not calculated."
        )
        st.markdown(
            "Enter the correct **runtime (h)** for each line. "
            "Confirm values with manufacturing/engineering."
        )
        bom = c["bom"].copy()
        zero_mask = pd.to_numeric(bom["runtime_h"], errors="coerce").fillna(0) == 0
        zero_rows = bom[zero_mask].copy()
        rt_cols = [c2 for c2 in ["line_id", "part_name", "material_id",
                                  "process_route", "runtime_h"] if c2 in zero_rows.columns]
        edited_rt = st.data_editor(
            zero_rows[rt_cols].reset_index(drop=True),
            column_config={
                "line_id":       st.column_config.TextColumn("Line ID", disabled=True),
                "part_name":     st.column_config.TextColumn("Part", disabled=True),
                "material_id":   st.column_config.TextColumn("Material", disabled=True),
                "process_route": st.column_config.TextColumn("Process route", disabled=True),
                "runtime_h":     st.column_config.NumberColumn("Runtime (h)", min_value=0.0, format="%.3f"),
            },
            use_container_width=True, num_rows="fixed", key="fix_runtime",
        )
        if st.button("💾 Save runtime values", key="save_runtime"):
            updated_bom = bom.copy()
            for _, row in edited_rt.iterrows():
                updated_bom.loc[updated_bom["line_id"] == row["line_id"], "runtime_h"] = row["runtime_h"]
            save_sheet(updated_bom, "bom")
            st.cache_data.clear()
            st.success("Saved — click 🔄 Re-check all.")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 3b — ZERO MASS BOM LINES
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(not c['zero_mass_lines'])} Fix BOM lines with zero or missing mass (kg)")

    if not c["zero_mass_lines"]:
        st.success("All BOM lines have a valid mass_kg value.")
    else:
        st.warning(
            f"{len(c['zero_mass_lines'])} BOM line(s) have mass_kg = 0 or blank — "
            "dry weight and €/kg calculations will be incorrect."
        )
        st.markdown(
            "Enter the correct **mass in kg** for each line. "
            "Use part drawings, weighing scales or material datasheet."
        )
        bom = c["bom"].copy()
        mass_mask = pd.to_numeric(bom["mass_kg"], errors="coerce").fillna(0) <= 0
        mass_rows = bom[mass_mask].copy()
        mass_cols = [col for col in ["line_id", "part_name", "material_id",
                                     "qty", "mass_kg"] if col in mass_rows.columns]
        edited_mass = st.data_editor(
            mass_rows[mass_cols].reset_index(drop=True),
            column_config={
                "line_id":     st.column_config.TextColumn("Line ID",   disabled=True),
                "part_name":   st.column_config.TextColumn("Part",      disabled=True),
                "material_id": st.column_config.TextColumn("Material",  disabled=True),
                "qty":         st.column_config.NumberColumn("Qty",     disabled=True),
                "mass_kg":     st.column_config.NumberColumn("Mass (kg)", min_value=0.0,
                                                              format="%.4f"),
            },
            use_container_width=True, num_rows="fixed", key="fix_mass",
        )
        if st.button("💾 Save mass values", key="save_mass"):
            updated_bom = bom.copy()
            for _, row in edited_mass.iterrows():
                updated_bom.loc[updated_bom["line_id"] == row["line_id"], "mass_kg"] = row["mass_kg"]
            save_sheet(updated_bom, "bom")
            st.cache_data.clear()
            st.success("Saved — click 🔄 Re-check all.")
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 4 — OVERHEAD % AND MARGIN %
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"⚙️ Review overhead % and margin % (Presets)")

    st.markdown(
        "Verify these rates match the **project approval**. "
        "Values are stored as decimals: 0.15 = 15 %."
    )
    procs = c["procs"].copy()
    rate_cols = [col for col in ["process_id", "machine_rate_eur_h", "labor_rate_eur_h",
                                  "overhead_pct", "margin_pct"] if col in procs.columns]
    edited_procs = st.data_editor(
        procs[rate_cols],
        column_config={
            "process_id":         st.column_config.TextColumn("Process", disabled=True),
            "machine_rate_eur_h": st.column_config.NumberColumn("Machine €/h", format="%.2f"),
            "labor_rate_eur_h":   st.column_config.NumberColumn("Labour €/h", format="%.2f"),
            "overhead_pct":       st.column_config.NumberColumn("Overhead (0–1)", min_value=0.0,
                                                                 max_value=1.0, format="%.2f"),
            "margin_pct":         st.column_config.NumberColumn("Margin (0–1)", min_value=0.0,
                                                                 max_value=1.0, format="%.2f"),
        },
        use_container_width=True, num_rows="fixed", key="fix_procs",
    )
    if st.button("💾 Save process rates", key="save_procs"):
        merged = procs.copy()
        for col in rate_cols:
            merged[col] = edited_procs[col].values
        save_sheet(merged, "processes")
        st.cache_data.clear()
        st.success("Saved — click 🔄 Re-check all.")
        st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 5 — DATA QUALITY ISSUES
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(c['dq_score'] >= 8)} Data Quality score: {c['dq_score']}/10 (need ≥ 8)")

    dq_items = [
        ("Material required fields",     not c["m_miss"],   c["m_miss"],   "pages/05_Data_Quality.py"),
        ("Material prices positive",      not c["m_pos"],    c["m_pos"],    "pages/05_Data_Quality.py"),
        ("Process required fields",       not c["p_miss"],   c["p_miss"],   "pages/05_Data_Quality.py"),
        ("Process rates positive",        not c["p_pos"],    c["p_pos"],    "pages/05_Data_Quality.py"),
        ("BOM required fields",           not c["b_miss"],   c["b_miss"],   "pages/05_Data_Quality.py"),
        ("BOM qty / mass positive",       not c["b_pos"],    c["b_pos"],    "pages/05_Data_Quality.py"),
        ("BOM process routes matched",    not c["b_no_rt"],  c["b_no_rt"],  "pages/05_Data_Quality.py"),
        ("BOM materials matched",         not c["b_no_mat"], c["b_no_mat"], "pages/05_Data_Quality.py"),
        ("No expired quotes",             not c["q_expired_ids"], c["q_expired_ids"], "pages/07_Supplier_Quotes.py"),
        ("Business rules pass",           c["rules_ok"],     [],            "pages/05_Data_Quality.py"),
    ]

    any_dq_fail = False
    for label, ok, bad_items, page in dq_items:
        icon = "✅" if ok else "❌"
        col_lbl, col_detail, col_btn = st.columns([3, 4, 1])
        col_lbl.markdown(f"{icon} {label}")
        if not ok and bad_items:
            col_detail.caption(
                f"{len(bad_items)} issue(s): "
                + ", ".join(str(x) for x in (bad_items[:5]))
                + ("…" if len(bad_items) > 5 else "")
            )
        if not ok:
            col_btn.page_link(page, label="Fix →", use_container_width=True)
            any_dq_fail = True

    if not any_dq_fail:
        st.success("All 10 data quality checks pass.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 6 — MISSING CRITICAL SUBSYSTEMS
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(not c['crit_missing'])} BOM completeness — critical subsystems")

    present_subs = detect_subsystems(c["bom"])
    sub_rows = []
    for prefix, info in WATERJET_SUBSYSTEMS.items():
        present = prefix in present_subs
        count   = present_subs.get(prefix, 0)
        sub_rows.append({
            "Subsystem":  f"{info['icon']} {info['name']}",
            "Critical":   "Yes" if info["critical"] else "—",
            "Status":     f"🟢 {count} lines" if present else "🔴 Missing",
            "Line prefix": prefix,
        })

    st.dataframe(pd.DataFrame(sub_rows), use_container_width=True, hide_index=True)

    if c["crit_missing"]:
        st.error(
            "Critical subsystem(s) missing: "
            + ", ".join(f"{i['icon']} {i['name']}" for _, i in c["crit_missing"])
            + "  \nAdd lines with the correct prefix to your BOM and re-upload."
        )
        st.page_link("pages/15_Bom_Import.py", label="→ Open BOM Import to re-upload",
                     use_container_width=False)
    else:
        st.success("All critical subsystems are present in the BOM.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  FIX SECTION 7 — ESTIMATE MATURITY
    # ══════════════════════════════════════════════════════════════════════════
    _section(f"{_badge(maturity in ('Definitive (±5%)', 'Firm'))} Estimate maturity")

    maturity_colour = {
        "RoM (±30%)":       "#f0a500",
        "Budget (±15%)":    "#ff7043",
        "Definitive (±5%)": "#42a5f5",
        "Firm":             "#66bb6a",
    }
    col = maturity_colour.get(maturity, "#888")
    st.markdown(
        f"Current maturity: "
        f"<span style='background:{col}22; border:1px solid {col}; border-radius:4px; "
        f"padding:2px 10px; color:{col}; font-weight:600'>{maturity}</span>",
        unsafe_allow_html=True,
    )

    prereqs = {
        "RoM (±30%)": [
            ("No critical subsystems missing",   not c["crit_missing"]),
            ("Material prices valid",             not c["m_pos"] and not c["m_miss"]),
            ("BOM process routes assigned",       not c["b_no_rt"]),
            ("BOM mass_kg filled",                not c["b_pos"]),
        ],
        "Budget (±15%)": [
            ("Data Quality ≥ 8/10",              c["dq_score"] >= 8),
            ("Quote coverage ≥ 80%",
             len(set(c["quotes"]["material_id"].unique()) if not c["quotes"].empty else set()) /
             max(len(c["mats"]), 1) * 100 >= 80),
            ("No expired quotes",                 not c["q_expired_ids"]),
            ("No zero-runtime BOM lines",         not c["zero_rt_lines"]),
            ("Overhead % and margin % confirmed", not c["p_miss"] and not c["p_pos"]),
        ],
    }
    current_prereqs = prereqs.get(maturity, [])
    all_prereqs_ok  = all(ok for _, ok in current_prereqs)

    if current_prereqs:
        st.markdown(f"**Prerequisites to advance to next level:**")
        for label, ok in current_prereqs:
            st.markdown(f"{'✅' if ok else '❌'} {label}")

    st.markdown("")
    new_maturity = st.selectbox(
        "Change maturity to",
        MATURITY_OPTIONS,
        index=MATURITY_OPTIONS.index(maturity),
        help="Only advance once all prerequisites above are ✅",
        key="maturity_select",
    )

    if not all_prereqs_ok and new_maturity != maturity:
        st.warning("⚠️ Not all prerequisites are resolved — resolve the items above before advancing.")

    target_cost = st.number_input(
        "Budget / target cost (€)",
        min_value=0.0,
        value=float(meta.get("target_cost", 0)),
        step=10_000.0, format="%.0f",
        help="Used to track gap-to-target on the dashboard and stakeholder report.",
        key="target_cost_input",
    )

    if st.button("💾 Save project settings", key="save_maturity"):
        save_project_meta(maturity=new_maturity, target_cost=target_cost)
        st.cache_data.clear()
        st.success(f"Saved — maturity set to **{new_maturity}**. Click 🔄 Re-check all.")
        st.rerun()


guard(main)
