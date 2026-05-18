"""Management & Procurement — cost breakdown dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

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
    k1.metric("Total Price", f"€ {total:,.2f}")
    k2.metric("Material Cost", f"€ {mat_sum:,.2f}", _pct(mat_sum, total))
    k3.metric("Process Cost", f"€ {proc_sum:,.2f}", _pct(proc_sum, total))
    k4.metric("Overhead", f"€ {oh_sum:,.2f}", _pct(oh_sum, total))
    k5.metric("Margin", f"€ {mar_sum:,.2f}", _pct(mar_sum, total))

    # ── Cost composition bar ──────────────────────────────────────────────────
    st.divider()
    st.subheader("📐 Cost Composition")

    comp = pd.DataFrame(
        {
            "Cost type": ["Material", "Process", "Overhead", "Margin"],
            "Amount (€)": [mat_sum, proc_sum, oh_sum, mar_sum],
            "Share (%)": [
                round(mat_sum / total * 100, 1),
                round(proc_sum / total * 100, 1),
                round(oh_sum / total * 100, 1),
                round(mar_sum / total * 100, 1),
            ],
        }
    )

    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(comp.set_index("Cost type")["Amount (€)"])
    with col_table:
        st.dataframe(
            comp.style.format({"Amount (€)": "€ {:,.2f}", "Share (%)": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )

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

        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.bar_chart(grp["total_cost"])
        with col_b:
            st.dataframe(
                grp[["material_cost", "process_cost", "overhead", "total_cost"]]
                .rename(
                    columns={
                        "material_cost": "Material",
                        "process_cost": "Process",
                        "overhead": "Overhead",
                        "total_cost": "Total",
                    }
                )
                .style.format("€ {:,.2f}"),
                use_container_width=True,
            )
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
            ).style.format("€ {:,.2f}"),
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
            "material_cost": "€ {:,.2f}",
            "process_cost":  "€ {:,.2f}",
            "overhead":      "€ {:,.2f}",
            "margin":        "€ {:,.2f}",
            "total_cost":    "€ {:,.2f}",
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
    st.bar_chart(detail[["material_cost", "process_cost", "overhead", "margin"]])

    with st.expander("📄 Full line detail"):
        cost_cols = ["material_cost", "process_cost", "overhead", "margin", "total_cost"]
        st.dataframe(
            detail.style.format({c: "€ {:,.2f}" for c in cost_cols if c in detail.columns}),
            use_container_width=True,
        )


guard(main)
