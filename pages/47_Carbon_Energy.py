"""
Carbon Footprint & Energy Consumption Tracker.

Energy data is sourced directly from the Processes sheet (energy_kw column —
machine power draw in kW). kWh per BOM line = qty x runtime_h x energy_kw.
Carbon is Scope 2 (purchased electricity) unless a supplier-specific emission
factor is used. Scope 3 upstream emissions require supplier data not held here.

Emission factors (kg CO2e / kWh):
  EU average grid  : 0.233  (EEA, 2023)
  India grid       : 0.816  (CEA, 2022-23)
  UK grid          : 0.207  (DESNZ, 2023)
  Netherlands grid : 0.270  (CBS/RVO, 2023)
  Custom           : user input
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import streamlit as st

from utils.completeness import WATERJET_SUBSYSTEMS
from utils.currency import fmt
from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_meta
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

# -- Emission factor presets (kg CO2e per kWh) --------------------------------
EMISSION_FACTORS: dict[str, float] = {
    "EU average grid (0.233)":        0.233,
    "India grid (0.816)":             0.816,
    "Netherlands grid (0.270)":       0.270,
    "UK grid (0.207)":                0.207,
    "Germany grid (0.380)":           0.380,
    "France grid (0.052 — nuclear)":  0.052,
    "100% renewables (0.000)":        0.000,
    "Custom":                         0.233,
}

# -- Waterjet subsystem prefix matching ---------------------------------------
_PREFIX_ORDER = sorted(WATERJET_SUBSYSTEMS.keys(), key=len, reverse=True)

def _scope_of(line_id: str) -> str:
    uid = str(line_id).upper()
    for p in _PREFIX_ORDER:
        if uid.startswith(p):
            return p
    return "_OTHER"

def _scope_label(sid: str) -> str:
    if sid in WATERJET_SUBSYSTEMS:
        info = WATERJET_SUBSYSTEMS[sid]
        return f"{info['icon']} {info['name']}"
    return "Other / Miscellaneous"


# =============================================================================
def main() -> None:
    st.set_page_config(page_title="Carbon & Energy", layout="wide", page_icon="🌱")
    inject_css()
    home_button()

    meta    = load_project_meta()
    project = meta.get("name", "")

    page_header(
        title="Carbon Footprint & Energy",
        icon="🌱",
        caption=(
            "Scope 2 electricity consumption and carbon footprint from BOM manufacturing operations. "
            "Energy data from Processes sheet (energy_kw). No supplier data required."
        ),
        project=project,
    )

    # -- Sidebar ---------------------------------------------------------------
    st.sidebar.divider()
    st.sidebar.subheader("Emission settings")

    preset_name = st.sidebar.selectbox(
        "Grid emission factor preset",
        list(EMISSION_FACTORS.keys()),
        index=0,
        help="kg CO2e per kWh. EU average is the default. "
             "Use India grid for production in India.",
    )
    if preset_name == "Custom":
        ef_kgco2_kwh = st.sidebar.number_input(
            "Custom emission factor (kg CO2e / kWh)",
            min_value=0.0, max_value=2.0, value=0.233, step=0.01, format="%.3f",
        )
    else:
        ef_kgco2_kwh = EMISSION_FACTORS[preset_name]
        st.sidebar.metric("Emission factor", f"{ef_kgco2_kwh:.3f} kg CO2e/kWh")

    energy_rate = st.sidebar.number_input(
        "Electricity cost (EUR/kWh)",
        min_value=0.0, max_value=2.0, value=0.20, step=0.01, format="%.2f",
        help="Used to reconcile energy cost in the BOM. Default 0.20 EUR/kWh.",
    )

    num_units = int(st.sidebar.number_input(
        "Production run (units)", min_value=1, value=1, step=1,
        help="Setup hours are amortised over this run size.",
    ))

    st.sidebar.divider()
    st.sidebar.info(
        "**Scope 2** (purchased electricity) is tracked here.\n\n"
        "**Scope 3** upstream emissions require supplier-specific data "
        "not held in the BOM — use a LCA tool for that.\n\n"
        "Reduce Scope 2 by:\n"
        "- Switching to CNC/machining centres with lower kW rating\n"
        "- Scheduling high-energy ops during off-peak hours\n"
        "- Sourcing from suppliers on renewable tariffs"
    )

    # -- Load data -------------------------------------------------------------
    @st.cache_data(ttl=30)
    def _load(rate: float, units: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        merged = apply_best_quotes(mats, quotes)
        # energy_rate=1.0 makes energy_cost column equal kWh directly
        df_kwh  = compute_costs(merged, procs, bom, num_units=units,
                                energy_rate_eur_kwh=1.0)
        df_cost = compute_costs(merged, procs, bom, num_units=units,
                                energy_rate_eur_kwh=rate)
        return df_kwh, df_cost

    try:
        df_kwh, df_cost = _load(energy_rate, num_units)
    except Exception as exc:
        st.error(f"Could not load BOM: {exc}")
        st.stop()

    # Ensure key columns exist
    for dcol in ("energy_cost",):
        if dcol not in df_kwh.columns:
            st.error(
                "No energy_kw data found in the Processes sheet. "
                "Add machine power draw (kW) to the Processes table first."
            )
            st.stop()

    # Merge line_id / part_name / process_route back if compute_costs dropped them
    for col in ("line_id", "part_name", "process_route"):
        if col not in df_kwh.columns:
            bom_raw = load_bom()
            if col in bom_raw.columns:
                df_kwh = df_kwh.merge(
                    bom_raw[["line_id", col]].drop_duplicates("line_id"),
                    on="line_id", how="left", suffixes=("", "_bom"),
                )
                df_cost = df_cost.merge(
                    bom_raw[["line_id", col]].drop_duplicates("line_id"),
                    on="line_id", how="left", suffixes=("", "_bom"),
                )

    df_kwh["kwh"]        = pd.to_numeric(df_kwh["energy_cost"],  errors="coerce").fillna(0.0)
    df_cost["total_cost"]= pd.to_numeric(df_cost["total_cost"],  errors="coerce").fillna(0.0)
    df_cost["energy_cost_eur"] = pd.to_numeric(df_cost["energy_cost"], errors="coerce").fillna(0.0)

    df_kwh["scope_id"]   = df_kwh["line_id"].map(_scope_of)
    df_kwh["scope_name"] = df_kwh["scope_id"].map(_scope_label)
    df_kwh["co2_kg"]     = df_kwh["kwh"] * ef_kgco2_kwh

    total_kwh        = float(df_kwh["kwh"].sum())
    total_co2_kg     = total_kwh * ef_kgco2_kwh
    total_co2_t      = total_co2_kg / 1000
    total_bom_cost   = float(df_cost["total_cost"].sum())
    total_energy_eur = float(df_cost["energy_cost_eur"].sum())
    energy_share_pct = total_energy_eur / total_bom_cost * 100 if total_bom_cost > 0 else 0.0

    # -- KPI row ---------------------------------------------------------------
    st.subheader("Summary")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total energy (kWh)",  f"{total_kwh:,.0f} kWh")
    k2.metric("Carbon footprint",    f"{total_co2_kg:,.0f} kg CO2e",
              delta=f"{total_co2_t:.2f} t CO2e", delta_color="off")
    k3.metric("Energy cost",         fmt(total_energy_eur, 0),
              delta=f"{energy_share_pct:.1f}% of BOM cost", delta_color="off")
    k4.metric("Emission factor",     f"{ef_kgco2_kwh:.3f} kg/kWh",
              delta=preset_name.split("(")[0].strip(), delta_color="off")
    k5.metric("Total BOM cost",      fmt(total_bom_cost, 0))

    if total_kwh == 0:
        st.warning(
            "No energy consumption data found. "
            "Check that the **energy_kw** column in the Processes sheet has values > 0. "
            "Go to **Data Quality** to inspect missing process fields."
        )

    st.divider()

    # -- Tabs ------------------------------------------------------------------
    tabs = st.tabs([
        "By Scope",
        "By Process",
        "BOM Line Detail",
        "Reduction Levers",
        "Scope 3 Context",
    ])

    # =========================================================================
    # TAB 1 -- BY SCOPE
    # =========================================================================
    with tabs[0]:
        st.subheader("Energy & carbon by waterjet subsystem scope")

        scope_agg = (
            df_kwh.groupby(["scope_id", "scope_name"])
            .agg(kwh=("kwh", "sum"), co2_kg=("co2_kg", "sum"), lines=("kwh", "count"))
            .reset_index()
            .sort_values("kwh", ascending=False)
        )
        scope_agg["co2_t"]    = scope_agg["co2_kg"] / 1000
        scope_agg["kwh_share"]= scope_agg["kwh"] / total_kwh * 100 if total_kwh > 0 else 0.0

        c1, c2 = st.columns([2, 1])
        with c1:
            chart_df = scope_agg.set_index("scope_name")[["kwh"]].rename(columns={"kwh": "kWh"})
            st.bar_chart(chart_df, color="#4CAF50", height=300,
                         use_container_width=True)
        with c2:
            disp = scope_agg[["scope_name", "kwh", "co2_kg", "kwh_share"]].copy()
            disp["kwh"]      = disp["kwh"].map(lambda x: f"{x:,.0f}")
            disp["co2_kg"]   = disp["co2_kg"].map(lambda x: f"{x:,.1f}")
            disp["kwh_share"]= disp["kwh_share"].map(lambda x: f"{x:.1f}%")
            st.dataframe(
                disp.rename(columns={
                    "scope_name": "Scope", "kwh": "kWh",
                    "co2_kg": "CO2e (kg)", "kwh_share": "Share",
                }),
                use_container_width=True, hide_index=True,
            )

        st.divider()
        st.subheader("Intensity: kWh per EUR of BOM cost")
        st.caption(
            "High kWh/EUR scopes are candidates for process optimisation or "
            "outsourcing to low-carbon suppliers."
        )

        # Join scope cost from df_cost
        scope_cost = (
            pd.DataFrame({"scope_id": df_cost["line_id"].map(_scope_of),
                          "cost": df_cost["total_cost"]})
            .groupby("scope_id")["cost"].sum()
            .reset_index()
        )
        intensity = scope_agg.merge(scope_cost, on="scope_id", how="left")
        intensity["kwh_per_eur"] = (
            intensity["kwh"] / intensity["cost"].replace(0, float("nan"))
        ).fillna(0.0)
        intensity_disp = intensity[["scope_name", "kwh", "cost", "kwh_per_eur"]].copy()
        intensity_disp["cost"]        = intensity_disp["cost"].map(lambda x: fmt(x, 0))
        intensity_disp["kwh"]         = intensity_disp["kwh"].map(lambda x: f"{x:,.0f}")
        intensity_disp["kwh_per_eur"] = intensity_disp["kwh_per_eur"].map(lambda x: f"{x:.3f}")
        st.dataframe(
            intensity_disp.rename(columns={
                "scope_name": "Scope", "kwh": "kWh",
                "cost": "BOM cost (EUR)", "kwh_per_eur": "kWh / EUR",
            }),
            use_container_width=True, hide_index=True,
        )

    # =========================================================================
    # TAB 2 -- BY PROCESS
    # =========================================================================
    with tabs[1]:
        st.subheader("Energy & carbon by process route")

        proc_col = "process_route" if "process_route" in df_kwh.columns else "process_id" if "process_id" in df_kwh.columns else None

        if proc_col:
            proc_agg = (
                df_kwh.groupby(proc_col)
                .agg(kwh=("kwh", "sum"), co2_kg=("co2_kg", "sum"), lines=(proc_col, "count"))
                .reset_index()
                .sort_values("kwh", ascending=False)
            )
            proc_agg["kwh_share"] = proc_agg["kwh"] / total_kwh * 100 if total_kwh > 0 else 0.0

            c1, c2 = st.columns([2, 1])
            with c1:
                pchart = proc_agg.set_index(proc_col)[["kwh"]].rename(columns={"kwh": "kWh"})
                st.bar_chart(pchart, color="#2196F3", height=300, use_container_width=True)
            with c2:
                pdisp = proc_agg[[proc_col, "kwh", "co2_kg", "kwh_share"]].copy()
                pdisp["kwh"]      = pdisp["kwh"].map(lambda x: f"{x:,.0f}")
                pdisp["co2_kg"]   = pdisp["co2_kg"].map(lambda x: f"{x:,.1f}")
                pdisp["kwh_share"]= pdisp["kwh_share"].map(lambda x: f"{x:.1f}%")
                st.dataframe(
                    pdisp.rename(columns={
                        proc_col: "Process", "kwh": "kWh",
                        "co2_kg": "CO2e (kg)", "kwh_share": "Share",
                    }),
                    use_container_width=True, hide_index=True,
                )

            # Energy kW reference from processes sheet
            st.divider()
            st.subheader("Process power ratings (from Processes sheet)")
            try:
                procs = load_processes()
                if "energy_kw" in procs.columns and "process_id" in procs.columns:
                    pkw = procs[procs["energy_kw"].notna() & (procs["energy_kw"] > 0)][
                        ["process_id", "energy_kw"]
                    ].sort_values("energy_kw", ascending=False)
                    if not pkw.empty:
                        st.dataframe(
                            pkw.rename(columns={"process_id": "Process", "energy_kw": "Power (kW)"}),
                            use_container_width=True, hide_index=True,
                        )
                    else:
                        st.info("No energy_kw values set in the Processes sheet.")
                else:
                    st.info("energy_kw column not found in Processes sheet.")
            except Exception:
                st.info("Could not load Processes sheet.")
        else:
            st.info("Process route column not available in the merged BOM.")

    # =========================================================================
    # TAB 3 -- BOM LINE DETAIL
    # =========================================================================
    with tabs[2]:
        st.subheader("Energy consumption per BOM line")
        st.caption(
            "Sorted by energy consumption descending. "
            "Lines with 0 kWh are bought-out or subcontracted parts (no in-house machining)."
        )

        line_disp = df_kwh.copy()
        line_disp["co2_kg"] = (line_disp["kwh"] * ef_kgco2_kwh).round(2)
        line_disp["kwh"]    = line_disp["kwh"].round(2)

        show_cols = [c for c in ["line_id", "part_name", "process_route",
                                  "scope_name", "kwh", "co2_kg"] if c in line_disp.columns]
        line_disp = line_disp[show_cols].sort_values("kwh", ascending=False)

        col_rename = {
            "line_id": "Line ID", "part_name": "Component",
            "process_route": "Process", "scope_name": "Scope",
            "kwh": "kWh", "co2_kg": "CO2e (kg)",
        }
        st.dataframe(
            line_disp.rename(columns=col_rename),
            use_container_width=True, hide_index=True,
        )

        # Download
        st.divider()
        try:
            csv_bytes = line_disp.rename(columns=col_rename).to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download energy breakdown (CSV)",
                data=csv_bytes,
                file_name=f"energy_breakdown_{date.today().isoformat()}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Could not generate CSV: {e}")

    # =========================================================================
    # TAB 4 -- REDUCTION LEVERS
    # =========================================================================
    with tabs[3]:
        st.subheader("Carbon reduction levers")

        # Identify top energy consumers (processes & scopes)
        if total_kwh > 0:
            top_scopes = (
                df_kwh.groupby("scope_name")["kwh"].sum()
                .sort_values(ascending=False).head(5)
            )
            top_proc_col = "process_route" if "process_route" in df_kwh.columns else None

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Top 5 scopes by energy")
                for scope, kwh in top_scopes.items():
                    pct = kwh / total_kwh * 100
                    st.markdown(f"- **{scope}**: {kwh:,.0f} kWh ({pct:.1f}%)")

            with c2:
                if top_proc_col:
                    top_procs = (
                        df_kwh.groupby(top_proc_col)["kwh"].sum()
                        .sort_values(ascending=False).head(5)
                    )
                    st.markdown("#### Top 5 processes by energy")
                    for proc, kwh in top_procs.items():
                        pct = kwh / total_kwh * 100
                        st.markdown(f"- **{proc}**: {kwh:,.0f} kWh ({pct:.1f}%)")

        st.divider()

        with st.container(border=True):
            st.markdown("#### Lever 1 — Switch to lower-carbon grid")
            eu_co2    = total_kwh * 0.233
            india_co2 = total_kwh * 0.816
            renew_co2 = 0.0
            current   = total_co2_kg
            st.markdown(f"""
| Grid | CO2e (kg) | vs current |
|------|-----------|-----------|
| 100% renewables | {renew_co2:,.0f} | {renew_co2 - current:+,.0f} kg |
| EU average | {eu_co2:,.0f} | {eu_co2 - current:+,.0f} kg |
| India grid | {india_co2:,.0f} | {india_co2 - current:+,.0f} kg |
            """)
            st.caption(
                "Procure electricity from a renewable energy supplier or install on-site solar. "
                "Effective immediately with no process changes required."
            )

        with st.container(border=True):
            st.markdown("#### Lever 2 — Process substitution (lower kW machines)")
            st.markdown("""
- Replace high-power machines (e.g. large lathes 45 kW) with modern machining centres (15–22 kW)
- Use near-net-shape castings to reduce machining allowances — directly cuts runtime_h
- CNC grinding: consider CBN wheels (lower depth-of-cut, faster cycle = shorter runtime)
- Waterjet cutting instead of milling for profile work: typically 15–25 kW vs 30–55 kW
            """)

        with st.container(border=True):
            st.markdown("#### Lever 3 — Outsource to low-carbon supplier")
            st.markdown("""
- Identify your top 3 energy-intensive processes (see tab **By Process**)
- Get suppliers to declare their grid mix / renewable certificate
- Prefer suppliers with ISO 50001 (energy management) or ESOS compliance
- Include carbon reporting as a supplier evaluation criterion in future tenders
            """)

        with st.container(border=True):
            st.markdown("#### Lever 4 — Batch production and setup optimisation")
            st.markdown("""
- Increase run size (`num_units` in sidebar): amortises setup_h over more parts,
  reducing energy per unit on setup-heavy processes
- Schedule high-kW operations during off-peak tariff windows (not a kWh saving,
  but reduces cost and grid-peak demand)
- Group similar materials / alloys to reduce furnace heating cycles
            """)

        st.info(
            "**Reporting note:** For customer sustainability reporting (CDP, GHG Protocol), "
            "these emissions are typically **Scope 2** (your purchased electricity). "
            "If outsourcing manufacturing, they become **Scope 3 Category 1** (purchased goods). "
            "Use the emission factor matching the manufacturing location.",
            icon="ℹ️",
        )

    # =========================================================================
    # TAB 5 -- SCOPE 3 CONTEXT
    # =========================================================================
    with tabs[4]:
        st.subheader("Scope 3 context — what this page covers vs what it doesn't")

        st.markdown("""
### GHG Protocol scope boundaries

| Scope | What | Covered here? |
|-------|------|--------------|
| **Scope 1** | Direct combustion (gas furnaces, diesels on-site) | No — requires fuel usage data not in BOM |
| **Scope 2** | Purchased electricity for machining / manufacturing | **YES — this page** |
| **Scope 3 Cat 1** | Upstream: materials extraction, raw steel/aluminium production | Partial — requires material-specific emission factors |
| **Scope 3 Cat 1** | Upstream: bought-out component manufacturing | No — requires supplier LCA |
| **Scope 3 Cat 4** | Upstream transport (inbound freight) | Partial — use Transport & Logistics page + transport EF |
| **Scope 3 Cat 11** | Use-phase emissions (fuel / CO2 from waterjet propulsion) | No — vessel operator data |
| **Scope 3 Cat 12** | End-of-life (scrap, disposal) | No — LCA tool required |

### Material carbon intensity (approximate, for reference)

| Material | kg CO2e / kg |
|----------|-------------|
| Primary aluminium | 8–12 |
| Recycled aluminium | 0.5–1.5 |
| Stainless steel (primary) | 4–6 |
| Stainless steel (recycled) | 1–2 |
| NAB casting (nickel-aluminium bronze) | 6–10 |
| Carbon fibre | 25–35 |
| Engineering rubber / elastomers | 3–5 |
| Hydraulic oil | 0.5–0.8 |

*Apply to BOM mass_kg values for a rough Scope 3 Cat 1 estimate. LCA software (SimaPro, OpenLCA) gives
rigorous results.*

### What to do next

1. **Scope 2 (this page):** Use the Reduction Levers tab to cut manufacturing electricity.
2. **Scope 3 Cat 1 materials:** Multiply `mass_kg` × material CO2e factor from table above.
3. **Scope 3 Cat 4 transport:** Use the Transport & Logistics page with freight ton-km data.
4. **Full LCA:** Export BOM to SimaPro / EcoInvent for a certified lifecycle assessment if
   required for eco-label, public procurement, or CBAM compliance.
        """)

        st.info(
            "**CBAM note (Carbon Border Adjustment Mechanism):** EU CBAM applies from 2026 "
            "to steel, aluminium, and certain manufactured goods imported into the EU. "
            "Waterjet impellers and structural castings in NAB / stainless may be in scope. "
            "Consult your trade compliance team.",
            icon="ℹ️",
        )


guard(main)
