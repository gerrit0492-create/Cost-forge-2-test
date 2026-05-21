"""
Executive Command Centre.
Single-screen cockpit — every key metric, signal and shortcut in one view.
Open this page first thing every morning; nothing else needed for a status check.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (
    load_bom, load_materials, load_processes, load_quotes,
    load_nre, load_risk, load_milestones, load_change_orders,
    load_actuals, load_transport, load_outbound,
)
from utils.nav import home_button
from utils.nre import nre_total
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes, expired_quote_materials
from utils.safe import guard
from utils.style import inject_css, page_header

REVISIONS_FILE = Path("data") / "quote_revisions.json"

_STATUS_COLOUR = {
    "green":  "#4CAF50",
    "amber":  "#FF9800",
    "red":    "#f44336",
    "blue":   "#2196F3",
    "grey":   "#9E9E9E",
}


# ── Tiny status dot ───────────────────────────────────────────────────────────
def _dot(colour: str) -> str:
    c = _STATUS_COLOUR.get(colour, colour)
    return f'<span style="color:{c};font-size:1.2rem;">●</span>'


def _pct_bar(pct: float, colour: str = "blue", height: int = 6) -> str:
    c = _STATUS_COLOUR.get(colour, colour)
    pct = min(max(pct, 0), 100)
    return (
        f'<div style="background:#1e2d40;border-radius:3px;height:{height}px;margin:4px 0">'
        f'<div style="background:{c};width:{pct:.0f}%;height:100%;border-radius:3px"></div>'
        f'</div>'
    )


def _kpi_card(label: str, value: str, sub: str = "", colour: str = "blue") -> str:
    c = _STATUS_COLOUR.get(colour, colour)
    return (
        f'<div style="background:#0f1e2e;border:1px solid {c}33;border-radius:8px;'
        f'padding:12px 16px;height:100%">'
        f'<div style="font-size:0.75rem;color:#8ba0b5;text-transform:uppercase;letter-spacing:.05em">'
        f'{label}</div>'
        f'<div style="font-size:1.35rem;font-weight:700;color:#e8edf2;margin:4px 0">{value}</div>'
        f'<div style="font-size:0.72rem;color:#8ba0b5">{sub}</div>'
        f'</div>'
    )


# ── Data loader (all in one, gracefully degraded) ─────────────────────────────
@st.cache_data(ttl=20)
def _all_data() -> dict:
    out: dict = {}

    # Core BOM costs
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
        out["bom_cost"]    = float(df["material_cost"].sum())
        out["proc_cost"]   = float(df["process_cost"].sum())
        out["oh_cost"]     = float(df["overhead"].sum())
        out["margin"]      = float(df["margin"].sum())
        out["sell"]        = float(df["total_cost"].sum())
        out["base_cost"]   = float(df["base_cost"].sum()) if "base_cost" in df.columns else (
            out["bom_cost"] + out["proc_cost"] + out["oh_cost"])
        out["bom_lines"]   = int(len(df))
        out["materials"]   = int(df["material_id"].nunique())
        out["expired"]     = expired_quote_materials(quotes)
        out["total_mats"]  = int(len(mats))
        out["quoted_mats"] = int(quotes["material_id"].nunique()) if not quotes.empty else 0
        qty_s = pd.to_numeric(bom["qty"], errors="coerce").fillna(1)
        out["mass_kg"] = float((qty_s * bom["mass_kg"].fillna(0)).sum())
    except Exception:
        pass

    # NRE
    try:
        nre_df = load_nre()
        out["nre_total"] = float(nre_total(nre_df))
        out["nre_lines"] = int(len(nre_df))
    except Exception:
        out["nre_total"] = 0.0

    # Transport
    try:
        transport_df = load_transport()
        out["has_transport"] = not transport_df.empty
    except Exception:
        out["has_transport"] = False

    # Risk
    try:
        risk_df = load_risk()
        if not risk_df.empty and "probability" in risk_df.columns:
            risk_df["_prob"]   = pd.to_numeric(risk_df["probability"],   errors="coerce").fillna(0)
            risk_df["_impact"] = pd.to_numeric(risk_df.get("impact_eur", risk_df.get("impact", 0)), errors="coerce").fillna(0)
            risk_df["_ev"]     = risk_df["_prob"] * risk_df["_impact"]
            open_risks         = risk_df[risk_df.get("status", pd.Series(["Open"] * len(risk_df))).str.lower().isin(["open", "active"])]
            out["risk_ev"]     = float(risk_df["_ev"].sum())
            out["open_risks"]  = int(len(open_risks))
        else:
            out["risk_ev"]    = 0.0
            out["open_risks"] = 0
    except Exception:
        out["risk_ev"]    = 0.0
        out["open_risks"] = 0

    # Milestones
    try:
        mil_df = load_milestones()
        if not mil_df.empty and "invoiced" in mil_df.columns:
            mil_df["_pct"]      = pd.to_numeric(mil_df.get("pct", 0), errors="coerce").fillna(0)
            mil_df["_invoiced"] = mil_df["invoiced"].astype(str).str.lower().isin(["true", "yes", "1", "invoiced"])
            out["milestones_total"]    = int(len(mil_df))
            out["milestones_invoiced"] = int(mil_df["_invoiced"].sum())
        else:
            out["milestones_total"]    = 0
            out["milestones_invoiced"] = 0
    except Exception:
        out["milestones_total"]    = 0
        out["milestones_invoiced"] = 0

    # Change orders
    try:
        co_df = load_change_orders()
        if not co_df.empty:
            approved     = co_df[co_df.get("status", pd.Series(dtype=str)).str.lower() == "approved"] \
                           if "status" in co_df.columns else co_df
            pending      = co_df[co_df.get("status", pd.Series(dtype=str)).str.lower() == "pending"] \
                           if "status" in co_df.columns else pd.DataFrame()
            co_rev       = pd.to_numeric(approved.get("revenue_delta_eur", pd.Series([0])), errors="coerce").fillna(0).sum()
            co_cost      = pd.to_numeric(approved.get("cost_delta_eur",    pd.Series([0])), errors="coerce").fillna(0).sum()
            out["co_approved"]    = int(len(approved))
            out["co_pending"]     = int(len(pending))
            out["co_rev_delta"]   = float(co_rev)
            out["co_cost_delta"]  = float(co_cost)
        else:
            out["co_approved"] = out["co_pending"] = 0
            out["co_rev_delta"] = out["co_cost_delta"] = 0.0
    except Exception:
        out["co_approved"] = out["co_pending"] = 0
        out["co_rev_delta"] = out["co_cost_delta"] = 0.0

    # Actuals
    try:
        act_df = load_actuals()
        if not act_df.empty and "actual_total_cost" in act_df.columns:
            out["actuals_lines"] = int(len(act_df))
            out["act_total"]     = float(pd.to_numeric(act_df["actual_total_cost"], errors="coerce").fillna(0).sum())
        else:
            out["actuals_lines"] = 0
            out["act_total"]     = 0.0
    except Exception:
        out["actuals_lines"] = 0
        out["act_total"]     = 0.0

    # Quote revisions
    try:
        if REVISIONS_FILE.exists():
            revs = json.loads(REVISIONS_FILE.read_text())
            out["rev_count"]   = len(revs)
            out["last_rev"]    = revs[-1].get("rev", "—") if revs else "—"
            out["last_rev_ts"] = revs[-1].get("timestamp", "")[:10] if revs else "—"
        else:
            out["rev_count"] = 0
            out["last_rev"]  = "—"
            out["last_rev_ts"] = "—"
    except Exception:
        out["rev_count"] = 0
        out["last_rev"]  = "—"
        out["last_rev_ts"] = "—"

    # Data quality score (simplified inline)
    try:
        mats2  = load_materials()
        bom2   = load_bom()
        quotes2 = load_quotes()
        checks = 0
        passes = 0

        # No-price check
        checks += 1
        has_mat = mats2["material_id"].notna() & (mats2["material_id"].astype(str).str.strip() != "")
        no_price_count = has_mat.sum() - (pd.to_numeric(mats2.loc[has_mat, "price_eur_kg"], errors="coerce") > 0).sum()
        if no_price_count == 0:
            passes += 1

        # Duplicate material IDs
        checks += 1
        if mats2["material_id"].duplicated().sum() == 0:
            passes += 1

        # Quote coverage
        checks += 1
        total_m = len(mats2)
        quoted_m = quotes2["material_id"].nunique() if not quotes2.empty else 0
        if total_m == 0 or quoted_m / total_m >= 0.8:
            passes += 1

        # Expired quotes
        checks += 1
        expired_c = len(expired_quote_materials(quotes2))
        if expired_c == 0:
            passes += 1

        # BOM duplicate IDs
        checks += 1
        if bom2["line_id"].duplicated().sum() == 0:
            passes += 1

        out["dq_score"] = int(passes / checks * 100) if checks > 0 else 0
        out["dq_checks"] = checks
        out["dq_passes"] = passes
    except Exception:
        out["dq_score"] = 0

    return out


def main() -> None:
    st.set_page_config(page_title="Command Centre", layout="wide", page_icon="🎯")
    inject_css()
    home_button()

    meta    = load_project_meta()
    project = meta.get("name", "Unnamed Project")
    maturity = meta.get("maturity", "—")
    customer = meta.get("customer", "")
    delivery_date = meta.get("delivery_date", "")
    target_cost = float(meta.get("target_cost", 0) or 0)

    page_header(
        title="Executive Command Centre",
        icon="🎯",
        caption="All key metrics, signals and workflow shortcuts — one screen, zero noise.",
        project=project,
        maturity=maturity,
    )

    # Refresh button
    col_r, _ = st.columns([1, 9])
    with col_r:
        if st.button("🔄 Refresh", help="Clear cached data"):
            st.cache_data.clear()
            st.rerun()

    d = _all_data()
    sell     = d.get("sell", 0.0)
    nre      = d.get("nre_total", 0.0)
    co_rev   = d.get("co_rev_delta", 0.0)
    revised  = sell + co_rev

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 0 — PROJECT IDENTITY BANNER
    # ══════════════════════════════════════════════════════════════════════════
    id_cols = st.columns([3, 2, 2, 2, 2, 2])
    id_cols[0].markdown(f"**🏗️ Project**  \n{project or '—'}")
    id_cols[1].markdown(f"**👤 Customer**  \n{customer or '—'}")
    id_cols[2].markdown(f"**📐 Maturity**  \n{maturity}")
    id_cols[3].markdown(f"**💰 Contract value**  \n{fmt(revised, 0)}")
    id_cols[4].markdown(f"**🎯 Target cost**  \n{fmt(target_cost, 0) if target_cost else '—'}")
    id_cols[5].markdown(f"**📅 Delivery**  \n{delivery_date or '—'}")
    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 1 — COST BUILD-UP MINI WATERFALL
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("💷 Cost build-up")

    bom_cost  = d.get("bom_cost", 0.0)
    proc_cost = d.get("proc_cost", 0.0)
    oh_cost   = d.get("oh_cost", 0.0)
    margin    = d.get("margin", 0.0)
    base_cost = d.get("base_cost", bom_cost + proc_cost + oh_cost)
    risk_ev   = d.get("risk_ev", 0.0)

    waterfall_steps = [
        ("Direct material",    bom_cost),
        ("Process / labour",   proc_cost),
        ("Overhead",           oh_cost),
        ("NRE (amortised)",    nre),
        ("Risk EV",            risk_ev),
        ("Margin",             margin),
    ]
    total_wf = sum(v for _, v in waterfall_steps)

    wf_cols = st.columns(len(waterfall_steps) + 1)
    cumul = 0.0
    for i, (label, val) in enumerate(waterfall_steps):
        pct = val / total_wf * 100 if total_wf > 0 else 0
        colour = "blue" if label != "Margin" else "green"
        cumul += val
        wf_cols[i].markdown(
            _kpi_card(label, fmt(val, 0), f"{pct:.1f}% of sell", colour),
            unsafe_allow_html=True,
        )
    # Sell total
    gap = revised - target_cost if target_cost > 0 else 0
    gap_col = "red" if gap > 0 else "green" if gap < 0 else "blue"
    wf_cols[-1].markdown(
        _kpi_card(
            "Sell price",
            fmt(revised, 0),
            f"{'▲ ' if gap > 0 else '▼ '}{fmt(abs(gap), 0)} vs target" if target_cost else "No target set",
            gap_col if target_cost else "blue",
        ),
        unsafe_allow_html=True,
    )

    # Sell-price progress bar vs target
    if target_cost > 0:
        pct_of_target = revised / target_cost * 100
        col_a = "red" if pct_of_target > 100 else "amber" if pct_of_target > 95 else "green"
        st.markdown(
            f"**Sell vs target: {pct_of_target:.1f}%**  "
            f"{_dot(col_a)} {'⚠️ Over target' if pct_of_target > 100 else '✅ Within target'}"
            + _pct_bar(min(pct_of_target, 100), col_a),
            unsafe_allow_html=True,
        )

    # Margin bar
    if base_cost > 0:
        mar_pct = margin / base_cost * 100
        mar_col = "red" if mar_pct < 5 else "amber" if mar_pct < 12 else "green"
        st.markdown(
            f"**Margin: {mar_pct:.1f}%**  {_dot(mar_col)}"
            + _pct_bar(mar_pct, mar_col),
            unsafe_allow_html=True,
        )

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 2 — FINANCIAL HEALTH | QUOTE STATUS | DATA QUALITY
    # ══════════════════════════════════════════════════════════════════════════
    col_fin, col_quote, col_dq = st.columns(3)

    with col_fin:
        st.subheader("💰 Financial health")

        mil_total    = d.get("milestones_total", 0)
        mil_invoiced = d.get("milestones_invoiced", 0)
        act_total    = d.get("act_total", 0.0)
        co_approved  = d.get("co_approved", 0)
        co_pending   = d.get("co_pending", 0)
        co_cost      = d.get("co_cost_delta", 0.0)

        # Milestone invoicing progress
        if mil_total > 0:
            mil_pct = mil_invoiced / mil_total * 100
            mil_col = "green" if mil_pct > 60 else "amber" if mil_pct > 20 else "blue"
            st.markdown(
                f"**Milestones invoiced: {mil_invoiced}/{mil_total}**  {_dot(mil_col)}"
                + _pct_bar(mil_pct, mil_col),
                unsafe_allow_html=True,
            )
        else:
            st.markdown("**Milestones:** Not configured")

        # Actuals vs budget
        if act_total > 0 and sell > 0:
            act_pct   = act_total / sell * 100
            act_colour = "red" if act_total > sell else "amber" if act_pct > 80 else "green"
            st.metric("Actuals recorded", fmt(act_total, 0),
                      delta=f"{act_pct:.0f}% of sell", delta_color="off")

        # Change orders
        co_col  = st.columns(2)
        co_col[0].metric("Approved COs",  co_approved,
                          delta=fmt(co_rev, 0) + " rev" if co_rev else None,
                          delta_color="normal")
        co_col[1].metric("Pending COs",   co_pending,
                          delta="⚠️ pending" if co_pending else "✅ clear",
                          delta_color="inverse" if co_pending else "off")

        # Net CO margin impact
        if co_rev or co_cost:
            co_margin_delta = co_rev - co_cost
            co_col2 = "green" if co_margin_delta >= 0 else "red"
            st.markdown(
                f"**CO net margin impact:** {_dot(co_col2)} {fmt(co_margin_delta, 0)}",
                unsafe_allow_html=True,
            )

    with col_quote:
        st.subheader("📜 Quote status")

        rev_count  = d.get("rev_count", 0)
        last_rev   = d.get("last_rev", "—")
        last_rev_ts = d.get("last_rev_ts", "—")
        expired    = d.get("expired", [])

        st.metric("Saved revisions", rev_count)
        st.markdown(f"**Latest snapshot:** {last_rev}  ({last_rev_ts})")
        st.markdown(f"**Estimate maturity:** {maturity}")

        # Quote expiry status
        exp_count = len(expired)
        exp_col = "red" if exp_count > 3 else "amber" if exp_count > 0 else "green"
        st.markdown(
            f"**Expired quotes:** {_dot(exp_col)} {exp_count}",
            unsafe_allow_html=True,
        )
        if expired:
            st.caption("Expired: " + ", ".join(expired[:5]) + ("…" if len(expired) > 5 else ""))

        # Quote coverage
        total_m  = d.get("total_mats", 0)
        quoted_m = d.get("quoted_mats", 0)
        if total_m > 0:
            cov_pct = quoted_m / total_m * 100
            cov_col = "green" if cov_pct >= 90 else "amber" if cov_pct >= 70 else "red"
            st.markdown(
                f"**Quote coverage:** {_dot(cov_col)} {quoted_m}/{total_m} ({cov_pct:.0f}%)"
                + _pct_bar(cov_pct, cov_col),
                unsafe_allow_html=True,
            )

        # NRE
        st.metric("NRE total", fmt(nre, 0),
                  delta=f"{d.get('nre_lines', 0)} work packages",
                  delta_color="off")

    with col_dq:
        st.subheader("✅ Data quality")

        dq_score  = d.get("dq_score", 0)
        dq_passes = d.get("dq_passes", 0)
        dq_checks = d.get("dq_checks", 5)
        open_risks = d.get("open_risks", 0)
        risk_ev   = d.get("risk_ev", 0.0)

        dq_col = "green" if dq_score >= 80 else "amber" if dq_score >= 50 else "red"
        st.markdown(
            f"**DQ score: {dq_score}%**  {_dot(dq_col)} ({dq_passes}/{dq_checks} checks pass)"
            + _pct_bar(dq_score, dq_col),
            unsafe_allow_html=True,
        )

        # Risk register
        risk_col = "red" if open_risks > 5 else "amber" if open_risks > 0 else "green"
        st.markdown(
            f"**Open risks:** {_dot(risk_col)} {open_risks}",
            unsafe_allow_html=True,
        )
        if risk_ev > 0:
            st.metric("Risk expected value", fmt(risk_ev, 0),
                      delta=f"{risk_ev / sell * 100:.1f}% of sell" if sell else None,
                      delta_color="inverse")

        # BOM stats
        st.markdown("---")
        bom_cols = st.columns(2)
        bom_cols[0].metric("BOM lines",  d.get("bom_lines", 0))
        bom_cols[1].metric("Materials",  d.get("materials", 0))
        mass = d.get("mass_kg", 0.0)
        if mass:
            st.metric("System dry weight", f"{mass:,.0f} kg")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 3 — QUICK ACTION SIGNALS
    # ══════════════════════════════════════════════════════════════════════════
    signals: list[tuple[str, str]] = []

    if d.get("expired"):
        signals.append(("🔴", f"{len(d['expired'])} expired quote(s) — renew before issuing firm price"))
    if d.get("open_risks", 0) > 0:
        signals.append(("🟠", f"{d['open_risks']} open risk(s) with EV {fmt(d['risk_ev'], 0)} — review mitigation"))
    if d.get("co_pending", 0) > 0:
        signals.append(("🟠", f"{d['co_pending']} change order(s) pending approval"))
    if target_cost and revised > target_cost:
        gap_pct = (revised - target_cost) / target_cost * 100
        signals.append(("🔴", f"Sell price is {gap_pct:.1f}% above target — cost reduction needed"))
    if base_cost and margin / base_cost < 0.08:
        signals.append(("🔴", f"Margin {margin / base_cost * 100:.1f}% is below 8% threshold"))
    if d.get("dq_score", 100) < 60:
        signals.append(("🟡", "Data quality below 60% — fix before customer submission"))
    if d.get("rev_count", 0) == 0:
        signals.append(("🔵", "No quote revisions saved — snapshot the current version in Quote Revisions"))
    if not signals:
        signals.append(("🟢", "No critical signals — all systems nominal"))

    with st.expander(f"{'🔴' if any(s[0] == '🔴' for s in signals) else '🟠' if any(s[0] == '🟠' for s in signals) else '🟢'} Action signals ({len(signals)})", expanded=True):
        for icon, msg in signals:
            st.markdown(f"{icon} {msg}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 4 — WORKFLOW NAVIGATOR
    # ══════════════════════════════════════════════════════════════════════════
    st.subheader("🗺️ Workflow navigator")

    sections = [
        ("1️⃣ Prepare", [
            ("pages/15_Bom_Import.py",            "📥 BOM Import"),
            ("pages/04_Materiaalbronnen.py",       "🧱 Materials"),
            ("pages/07_Supplier_Quotes.py",        "🏭 Supplier Quotes"),
            ("pages/03_Presets.py",                "⚙️ Presets"),
        ]),
        ("2️⃣ Calculate", [
            ("pages/01_Quick_Cost.py",             "⚡ Quick Cost"),
            ("pages/16_Routing_Kosten.py",         "🛠️ Routing Costs"),
            ("pages/32_Item_Costing.py",           "🔢 Item Costing"),
            ("pages/30_Bore_Scale.py",             "📐 Size Scale"),
        ]),
        ("3️⃣ Analyse", [
            ("pages/28_Line_Cost_Detail.py",       "🔍 Line Detail"),
            ("pages/06_Scenario_Planner.py",       "🧭 Scenarios"),
            ("pages/27_Management_Dashboard.py",   "📊 Management"),
            ("pages/05_Data_Quality.py",           "✅ Data Quality"),
        ]),
        ("4️⃣ Quote", [
            ("pages/29_Quote_Sheet.py",            "🧾 Quote Sheet"),
            ("pages/44_Quote_Revisions.py",        "📜 Revisions"),
            ("pages/18_Offerte_DOCX.py",           "📝 DOCX"),
            ("pages/19_Offerte_PDF.py",            "🖨️ PDF"),
        ]),
        ("5️⃣ Toolbox", [
            ("pages/35_Transport_Logistics.py",    "🚢 Transport"),
            ("pages/36_Engineering_NRE.py",        "🔬 NRE"),
            ("pages/37_Volume_Analysis.py",        "📈 Volume"),
            ("pages/38_Escalation_Risk.py",        "📉 Risk"),
            ("pages/39_Full_Cost_Summary.py",      "🌊 Waterfall"),
        ]),
        ("6️⃣ Lifecycle", [
            ("pages/40_Contract_Cashflow.py",      "💰 Cash Flow"),
            ("pages/41_Change_Orders.py",          "🔄 Change Orders"),
            ("pages/42_Project_Closeout.py",       "📁 Close-out"),
            ("pages/43_Spare_Parts.py",            "🔩 Spare Parts"),
        ]),
    ]

    nav_cols = st.columns(len(sections))
    for col, (section_title, pages) in zip(nav_cols, sections):
        with col:
            st.markdown(f"**{section_title}**")
            for page_path, label in pages:
                try:
                    st.page_link(page_path, label=label, use_container_width=True)
                except Exception:
                    st.markdown(f"- {label}")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 5 — COST STACK MINI-CHART (bar)
    # ══════════════════════════════════════════════════════════════════════════
    if sell > 0:
        with st.expander("📊 Cost element split", expanded=False):
            chart_data = pd.DataFrame({
                "Element": ["Material", "Process", "Overhead", "NRE", "Risk EV", "Margin"],
                "€": [bom_cost, proc_cost, oh_cost, nre, risk_ev, margin],
            }).set_index("Element")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.bar_chart(chart_data, color="#2196F3", height=200)
            with c2:
                chart_data["Share"] = chart_data["€"] / total_wf * 100
                chart_data["€ fmt"] = chart_data["€"].map(lambda x: fmt(x, 0))
                chart_data["Share fmt"] = chart_data["Share"].map(lambda x: f"{x:.1f}%")
                st.dataframe(
                    chart_data[["€ fmt", "Share fmt"]].rename(
                        columns={"€ fmt": "Amount", "Share fmt": "Share"}
                    ),
                    use_container_width=True,
                )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.caption(
        "🎯 Command Centre — auto-refreshes every 20 s. "
        "All figures from live workbook. Click any link above to drill in."
    )


guard(main)
