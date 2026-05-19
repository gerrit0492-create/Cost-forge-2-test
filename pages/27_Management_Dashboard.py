"""Management & Procurement — cost breakdown dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.nav import home_button
from utils.safe import guard


def _pct(part: float, total: float) -> str:
    return f"{part / total * 100:.1f}%" if total else "—"


def main() -> None:
    home_button()
    st.title("📊 Management Dashboard — Cost Breakdown")
    st.caption(
        "Overview of material, process, overhead and margin costs for management and procurement."
    )

    mats = load_materials()
    procs = load_processes()
    quotes = load_quotes()
    bom = load_bom()

    df = compute_costs(apply_best_quotes(mats, quotes), procs, bom)

    total = df["total_cost"].sum()
    mat_sum = df["material_cost"].sum()
    proc_sum = df["process_cost"].sum()
    oh_sum = df["overhead"].sum()
    mar_sum = df["margin"].sum()

    # ── KPI row ───────────────────────────────────────────────────────────────
    st.subheader("💶 Total Overview")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Selling price",  fmt(total, 2))
    k2.metric("Material (purchase)", fmt(mat_sum, 2),  f"{mat_sum/total*100:.1f}% of sell")
    k3.metric("Machine + Labour",    fmt(proc_sum, 2), f"{proc_sum/total*100:.1f}% of sell")
    k4.metric("Overhead",            fmt(oh_sum, 2),   f"{oh_sum/total*100:.1f}% of sell")
    k5.metric("Margin",              fmt(mar_sum, 2),  f"{mar_sum/total*100:.1f}% of sell")

    # ── Cost composition ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📐 Cost Composition")

    comp = pd.DataFrame({
        "Cost element":  ["Material (purchase)", "Machine + Labour", "Overhead", "Margin"],
        "EUR":           [mat_sum, proc_sum, oh_sum, mar_sum],
        "Share of sell": [mat_sum/total, proc_sum/total, oh_sum/total, mar_sum/total],
    })

    # Stacked single-bar — one row, four columns → all segments visible
    stacked = pd.DataFrame(
        [[mat_sum, proc_sum, oh_sum, mar_sum]],
        columns=["Material", "Process", "Overhead", "Margin"],
        index=["Cost build-up"],
    )
    st.bar_chart(stacked, color=["#2196F3", "#FF9800", "#9C27B0", "#4CAF50"])

    comp_disp = comp.copy()
    comp_disp["EUR"] = comp_disp["EUR"].map(lambda x: fmt(x, 0))
    comp_disp["Share of sell"] = comp_disp["Share of sell"].map(lambda x: f"{x*100:.1f}%")
    st.dataframe(comp_disp, use_container_width=True, hide_index=True)

    # ── By commodity ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🧱 Costs per material group")

    if "commodity" in df.columns:
        grp = (
            df.groupby("commodity", dropna=False)[
                ["material_cost", "process_cost", "overhead", "margin", "total_cost"]
            ]
            .sum()
            .sort_values("total_cost", ascending=False)
            .round(2)
        )
        grp.index.name = "Material group"

        # Stacked bar: each commodity shows Material + Process + Overhead + Margin
        grp_stacked = grp[["material_cost", "process_cost", "overhead", "margin"]].rename(
            columns={"material_cost": "Material", "process_cost": "Process",
                     "overhead": "Overhead", "margin": "Margin"}
        )
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.bar_chart(grp_stacked)
        with col_b:
            tbl = grp[["material_cost", "process_cost", "overhead", "total_cost"]].rename(
                columns={"material_cost": "Material €", "process_cost": "Process €",
                         "overhead": "Overhead €", "total_cost": "Total €"}
            )
            st.dataframe(tbl.style.format(lambda x: fmt(x, 0)), use_container_width=True)
    else:
        st.info("No commodity column present in material data.")

    # ── By process route ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("⚙️ Costs per process")

    proc_grp = (
        df.groupby("process_route")[["process_cost", "overhead", "total_cost"]]
        .sum()
        .sort_values("process_cost", ascending=False)
        .round(2)
    )
    proc_grp.index.name = "Process"

    col_c, col_d = st.columns([2, 1])
    with col_c:
        st.bar_chart(proc_grp["process_cost"])
    with col_d:
        st.dataframe(
            proc_grp.rename(
                columns={
                    "process_cost": "Process cost",
                    "overhead": "Overhead",
                    "total_cost": "Total",
                }
            ).style.format(lambda x: fmt(x, 2)),
            use_container_width=True,
        )

    # ── Top 10 most expensive lines ───────────────────────────────────────────
    st.divider()
    st.subheader("🔝 Top 10 most expensive BOM lines")

    top10 = (
        df.nlargest(10, "total_cost")[
            [
                "line_id",
                "material_id",
                "qty",
                "mass_kg",
                "material_cost",
                "process_cost",
                "overhead",
                "margin",
                "total_cost",
            ]
        ]
        .round(2)
        .reset_index(drop=True)
    )
    st.dataframe(
        top10.style.format({
            "material_cost": lambda x: fmt(x, 2),
            "process_cost":  lambda x: fmt(x, 2),
            "overhead":      lambda x: fmt(x, 2),
            "margin":        lambda x: fmt(x, 2),
            "total_cost":    lambda x: fmt(x, 2),
            "mass_kg":       "{:.2f} kg",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # ── Material vs process per line ─────────────────────────────────────────
    st.divider()
    st.subheader("📋 Material vs process per BOM line")

    detail = (
        df[
            [
                "line_id",
                "material_id",
                "material_cost",
                "process_cost",
                "overhead",
                "margin",
                "total_cost",
            ]
        ]
        .set_index("line_id")
        .round(2)
    )
    # Show material and process side-by-side so material cost is not swamped
    ch1, ch2 = st.columns(2)
    with ch1:
        st.caption("Material purchase cost per line")
        st.bar_chart(detail["material_cost"])
    with ch2:
        st.caption("Machine + Labour cost per line")
        st.bar_chart(detail["process_cost"])

    with st.expander("📄 Full line detail (all cost columns)"):
        cost_cols = ["material_cost", "process_cost", "overhead", "margin", "total_cost"]
        tbl = detail[cost_cols].rename(columns={
            "material_cost": "Material €", "process_cost": "Process €",
            "overhead": "Overhead €", "margin": "Margin €", "total_cost": "Total €",
        })
        st.dataframe(tbl.style.format(lambda x: fmt(x, 0)), use_container_width=True)

    # ── Dry weight by subsystem ───────────────────────────────────────────────
    st.divider()
    st.subheader("⚖️ Dry weight summary")

    qty_s = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
    total_kg = (qty_s * df["mass_kg"].fillna(0)).sum()
    st.metric("Total dry weight", f"{total_kg:,.0f} kg")

    if "subsystem" not in df.columns:
        from utils.completeness import WATERJET_SUBSYSTEMS as _WS
        def _prefix(lid):
            u = str(lid).upper()
            for p in sorted(_WS, key=len, reverse=True):
                if u.startswith(p):
                    return p
            return "?"
        df["subsystem"] = df["line_id"].apply(_prefix)

    wt_grp = (
        df.assign(line_mass=qty_s * df["mass_kg"].fillna(0))
        .groupby("subsystem")["line_mass"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"subsystem": "Subsystem", "line_mass": "Mass (kg)"})
    )
    wt_grp["Share %"] = (wt_grp["Mass (kg)"] / total_kg * 100).map(lambda x: f"{x:.1f}%")
    wt_grp["Mass (kg)"] = wt_grp["Mass (kg)"].map(lambda x: f"{x:,.1f}")

    col_wt, col_wttbl = st.columns([2, 1])
    with col_wt:
        wt_chart = df.assign(line_mass=qty_s * df["mass_kg"].fillna(0)).groupby("subsystem")["line_mass"].sum()
        st.bar_chart(wt_chart)
    with col_wttbl:
        st.dataframe(wt_grp, use_container_width=True, hide_index=True)

    # ── Material purchase summary ─────────────────────────────────────────────
    st.divider()
    st.subheader("🧱 Material purchase summary")
    st.caption("Total purchase quantity and cost per material — for procurement / PO planning.")

    purch = df.copy()
    purch["purchase_kg"] = qty_s * (purch["mass_kg"].fillna(0) / purch.get("yield_factor", 1).fillna(1).clip(lower=0.05))
    purch_grp = (
        purch.groupby("material_id")
        .agg(purchase_kg=("purchase_kg", "sum"), material_cost=("material_cost", "sum"))
        .reset_index()
        .sort_values("material_cost", ascending=False)
    )
    if "supplier" in purch.columns:
        sup = purch.groupby("material_id")["supplier"].first().reset_index()
        purch_grp = purch_grp.merge(sup, on="material_id", how="left")
    if "lead_time_days" in purch.columns:
        lt = purch.groupby("material_id")["lead_time_days"].max().reset_index()
        purch_grp = purch_grp.merge(lt, on="material_id", how="left")

    purch_grp.rename(columns={
        "material_id": "Material", "purchase_kg": "Purchase qty (kg)",
        "material_cost": "Purchase cost (€)", "supplier": "Supplier",
        "lead_time_days": "Lead time (days)",
    }, inplace=True)
    st.dataframe(
        purch_grp.style.format({
            "Purchase qty (kg)": "{:,.1f}", "Purchase cost (€)": lambda x: fmt(x, 2),
        }),
        use_container_width=True, hide_index=True,
    )

    # ── Manufacturing hours by process ────────────────────────────────────────
    st.divider()
    st.subheader("🕐 Manufacturing hours by process centre")
    st.caption("Total shop hours consumed — for capacity planning and subcontract RFQs.")

    qty_n = pd.to_numeric(df["qty"], errors="coerce").fillna(1)
    hours_grp = (
        df.assign(total_h=qty_n * df["runtime_h"].fillna(0))
        .groupby("process_route")
        .agg(total_h=("total_h", "sum"), process_cost=("process_cost", "sum"))
        .reset_index()
        .sort_values("total_h", ascending=False)
        .rename(columns={
            "process_route": "Process", "total_h": "Total hours",
            "process_cost": "Process cost (€)",
        })
    )
    col_h, col_htbl = st.columns([2, 1])
    with col_h:
        st.bar_chart(hours_grp.set_index("Process")["Total hours"])
    with col_htbl:
        st.dataframe(
            hours_grp.style.format({
                "Total hours": "{:,.1f} h", "Process cost (€)": lambda x: fmt(x, 2),
            }),
            use_container_width=True, hide_index=True,
        )

    # ── Lead time analysis ────────────────────────────────────────────────────
    st.divider()
    st.subheader("⏱️ Procurement lead time analysis")

    if "lead_time_days" in df.columns:
        lt_df = (
            df[["material_id", "lead_time_days"]].dropna()
            .groupby("material_id")["lead_time_days"].max()
            .reset_index()
            .sort_values("lead_time_days", ascending=False)
            .rename(columns={"material_id": "Material", "lead_time_days": "Lead time (days)"})
        )
        if "supplier" in df.columns:
            sup = df.groupby("material_id")["supplier"].first().reset_index().rename(
                columns={"material_id": "Material", "supplier": "Supplier"})
            lt_df = lt_df.merge(sup, on="Material", how="left")

        max_lt = lt_df["Lead time (days)"].max()
        gating = lt_df[lt_df["Lead time (days)"] == max_lt]["Material"].tolist()
        st.warning(
            f"**Critical path material:** {', '.join(gating)} — **{int(max_lt)} days** lead time.  \n"
            "Order this material first to avoid delivery delays."
        )
        st.dataframe(lt_df, use_container_width=True, hide_index=True)
    else:
        st.info("Lead time data not available — add supplier quotes with `lead_time_days` to see this analysis.")


guard(main)
