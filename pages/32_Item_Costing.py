from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from utils.currency import fmt, fmt_delta
from utils.io import load_materials, load_processes, load_quotes, df_to_excel_bytes
from utils.nav import home_button
from utils.quotes import apply_best_quotes

st.set_page_config(page_title="Item Costing", layout="wide", page_icon="🔢")
home_button()
st.title("🔢 Item Costing")
st.caption("Price a single part end-to-end: full process routing, overhead, margin, volume breaks and surcharges.")

# ── Load reference data ───────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _refs():
    mats  = apply_best_quotes(load_materials(), load_quotes())
    procs = load_processes()
    return mats, procs

mats_df, procs_df = _refs()

mat_ids  = mats_df["material_id"].tolist()
proc_ids = procs_df["process_id"].tolist()

def _mat_row(mid: str) -> pd.Series:
    rows = mats_df[mats_df["material_id"] == mid]
    return rows.iloc[0] if not rows.empty else pd.Series(dtype=float)

def _proc_row(pid: str) -> pd.Series:
    rows = procs_df[procs_df["process_id"] == pid]
    return rows.iloc[0] if not rows.empty else pd.Series(dtype=float)

# ── Yield factor hints ────────────────────────────────────────────────────────
YIELD_HINTS = {
    "5AX_MILL_IMP":   0.35,
    "CNC_LATHE_PREC": 0.60,
    "CNC_MILL_3AX":   0.75,
    "PREC_BORE":       0.85,
    "SURF_GRIND":      0.92,
    "SAND_CAST":       0.60,
    "TIG_WELD_316":    0.90,
    "PLASMA_CUT":      0.85,
    "WATERJET_CUT":    0.95,
    "FINAL_ASSEMBLY":  1.00,
    "NDT_INSPECT":     1.00,
    "PRESSURE_TEST":   1.00,
    "DYN_BALANCE":     1.00,
    "HARD_CHROME":     1.00,
    "POWDER_COAT":     1.00,
    "CNC_LATHE_GEN":   0.65,
    "CNC_MILL_4AX":    0.70,
    "TURN_MILL":       0.60,
    "DEEP_HOLE_DRILL": 0.88,
    "HONING":          0.95,
    "LAPPING":         0.96,
    "JIG_BORE":        0.90,
    "THREAD_GRIND":    0.92,
    "GEAR_CUT":        0.80,
    "MIG_WELD":        0.92,
    "PIPE_WELD":       0.90,
    "WELD_OVERLAY":    0.88,
    "LASER_WELD":      0.95,
    "LASER_CUT":       0.92,
    "FLAME_CUT":       0.82,
    "PRESS_BRAKE":     0.96,
    "ROLL_FORM":       0.94,
    "INVEST_CAST":     0.65,
    "CENTRIFUGAL":     0.70,
    "FORGING":         0.75,
    "HEAT_TREAT":      1.00,
    "SHOT_PEEN":       1.00,
    "HOT_DIP_GALV":    1.00,
    "NITRIDING":       1.00,
    "RUBBER_BOND":     0.95,
    "CMM_INSPECT":     1.00,
    "RADIOGRAPHY":     1.00,
    "FLOW_TEST":       1.00,
    "LEAK_TEST":       1.00,
    "VIBRATION_TEST":  1.00,
}

SURFACE_TREATMENTS = {
    "None":                     {"cost_eur": 0,    "label": ""},
    "Zinc primer + epoxy coat": {"cost_eur": 180,  "label": "Paint"},
    "Hard chrome plate":        {"cost_eur": 420,  "label": "Chrome"},
    "Electroless nickel":       {"cost_eur": 340,  "label": "E-Ni"},
    "Anodise (Al alloys)":      {"cost_eur": 120,  "label": "Anodise"},
    "Hot-dip galvanise":        {"cost_eur": 95,   "label": "HDG"},
    "Powder coat":              {"cost_eur": 160,  "label": "Powder"},
}

CERT_SURCHARGES = {
    "None":           0.00,
    "DNV / GL":       0.08,
    "Lloyd's (LRS)":  0.08,
    "Bureau Veritas": 0.07,
    "ABS":            0.07,
}

# ── Form ──────────────────────────────────────────────────────────────────────
st.subheader("1 · Part definition")
col_a, col_b, _ = st.columns(3)
part_name = col_a.text_input("Part name", value="New part", placeholder="e.g. Impeller body")
qty_base  = col_b.number_input("Quantity (units)", min_value=1, max_value=500, value=1)

st.subheader("2 · Material")
mc1, mc2, mc3, mc4 = st.columns(4)
mat_id   = mc1.selectbox("Material", mat_ids)
mat      = _mat_row(mat_id)
net_mass = mc2.number_input("Net / finished mass (kg)", min_value=0.0, value=10.0, step=0.5)
yield_fac = mc3.number_input(
    "Yield factor",
    min_value=0.05, max_value=1.0,
    value=float(YIELD_HINTS.get("CNC_LATHE_PREC", 0.70)),
    step=0.01,
    help="Finished mass / purchase mass. 0.60 = 60% of purchased material ends up in the part.",
)
price_kg = mc4.number_input(
    "Price (€/kg)",
    min_value=0.0,
    value=float(mat.get("price_eur_per_kg", 5.0)),
    step=0.10,
    help="Pre-filled from best supplier quote. Override if needed.",
)

purchase_mass = net_mass / max(yield_fac, 0.01)
mat_cost      = purchase_mass * price_kg

mi1, mi2, mi3 = st.columns(3)
mi1.metric("Purchase mass (kg)", f"{purchase_mass:,.2f}")
mi2.metric("Yield loss (kg)",     f"{purchase_mass - net_mass:,.2f}")
mi3.metric("Material cost",       fmt(mat_cost, 2))

# ── Step 3: Process routing ───────────────────────────────────────────────────
st.subheader("3 · Process routing")
st.caption(
    "Add one row per operation in sequence. "
    "Rates pre-fill from the process library — override per step. "
    "Set **Subcon €** to replace machine+labour with a fixed subcontract price for that step."
)

def _default_step(pid: str | None = None) -> dict:
    pid = pid or (proc_ids[0] if proc_ids else "")
    p   = _proc_row(pid)
    return {
        "process_id":         pid,
        "runtime_h":          1.0,
        "setup_h":            0.5,
        "machine_rate_eur_h": float(p.get("machine_rate_eur_h", 90.0)),
        "labor_rate_eur_h":   float(p.get("labor_rate_eur_h",  58.0)),
        "subcon_eur":         0.0,
    }

if "ic_steps" not in st.session_state:
    first_pid = proc_ids[0] if proc_ids else ""
    p0 = _proc_row(first_pid)
    st.session_state["ic_steps"] = pd.DataFrame([{
        "process_id":         first_pid,
        "runtime_h":          2.0,
        "setup_h":            1.0,
        "machine_rate_eur_h": float(p0.get("machine_rate_eur_h", 90.0)),
        "labor_rate_eur_h":   float(p0.get("labor_rate_eur_h",  58.0)),
        "subcon_eur":         0.0,
    }])

btn_add, btn_clear, _ = st.columns([1, 1, 5])
if btn_add.button("➕ Add operation"):
    new_row = pd.DataFrame([_default_step()])
    st.session_state["ic_steps"] = pd.concat(
        [st.session_state["ic_steps"], new_row], ignore_index=True
    )
if btn_clear.button("🗑️ Clear routing"):
    st.session_state["ic_steps"] = pd.DataFrame([_default_step()])

steps_df = st.data_editor(
    st.session_state["ic_steps"],
    column_config={
        "process_id":         st.column_config.SelectboxColumn(
            "Process route", options=proc_ids, required=True, width="medium"
        ),
        "runtime_h":          st.column_config.NumberColumn(
            "Runtime h/unit", min_value=0.0, step=0.25, format="%.2f"
        ),
        "setup_h":            st.column_config.NumberColumn(
            "Setup h (total)", min_value=0.0, step=0.25, format="%.2f",
            help="One-off setup time, shared across all units in the batch."
        ),
        "machine_rate_eur_h": st.column_config.NumberColumn(
            "Machine €/h", min_value=0.0, step=5.0, format="%.0f"
        ),
        "labor_rate_eur_h":   st.column_config.NumberColumn(
            "Labour €/h", min_value=0.0, step=2.0, format="%.0f"
        ),
        "subcon_eur":         st.column_config.NumberColumn(
            "Subcon € / unit", min_value=0.0, step=10.0, format="%.0f",
            help="If > 0, replaces machine+labour for this step with a fixed subcontract price."
        ),
    },
    num_rows="dynamic",
    use_container_width=True,
    key="steps_editor",
)
st.session_state["ic_steps"] = steps_df

# Update yield hint based on first process step
first_proc_id = steps_df["process_id"].iloc[0] if not steps_df.empty else ""
_hint = YIELD_HINTS.get(first_proc_id)
if _hint and abs(_hint - yield_fac) > 0.01:
    st.caption(f"💡 Typical yield factor for **{first_proc_id}**: `{_hint:.2f}` — adjust in step 2 if needed.")

# Routing summary metrics
total_runtime = float(steps_df["runtime_h"].sum()) if not steps_df.empty else 0.0
total_setup   = float(steps_df["setup_h"].sum())   if not steps_df.empty else 0.0
rs1, rs2, rs3 = st.columns(3)
rs1.metric("Operations",       len(steps_df))
rs2.metric("Total runtime",    f"{total_runtime:.2f} h/unit")
rs3.metric("Total setup",      f"{total_setup:.2f} h")

st.subheader("4 · Overhead & margin")
rt3, rt4 = st.columns(2)

# Use first step's process defaults as reference for overhead/margin
ref_proc = _proc_row(first_proc_id)
overhead_pct = rt3.number_input(
    "Overhead %", min_value=0.0, max_value=100.0,
    value=float(ref_proc.get("overhead_pct", 0.18)) * 100, step=1.0,
) / 100.0
margin_pct = rt4.number_input(
    "Margin %", min_value=0.0, max_value=80.0,
    value=float(ref_proc.get("margin_pct", 0.18)) * 100, step=1.0,
) / 100.0

st.subheader("5 · Surcharges")
su1, su2, su3, su4 = st.columns(4)
ndt_h       = su1.number_input("NDT inspection (h)", min_value=0.0, value=0.0, step=0.5)
surface     = su2.selectbox("Surface treatment", list(SURFACE_TREATMENTS.keys()))
cert_class  = su3.selectbox("Classification", list(CERT_SURCHARGES.keys()))
freight_eur = su4.number_input("Packaging & freight (€)", min_value=0.0, value=0.0, step=25.0)

st.subheader("6 · Volume discount schedule")
st.caption("Adjust discounts at each quantity break. Setup amortisation is automatic.")
vd1, vd2, vd3, vd4 = st.columns(4)
disc_5  = vd1.number_input("Discount at  5 units (%)", 0.0, 30.0, 3.0, 0.5) / 100
disc_10 = vd2.number_input("Discount at 10 units (%)", 0.0, 30.0, 5.0, 0.5) / 100
disc_25 = vd3.number_input("Discount at 25 units (%)", 0.0, 30.0, 8.0, 0.5) / 100
disc_50 = vd4.number_input("Discount at 50 units (%)", 0.0, 30.0, 12.0, 0.5) / 100

VOLUME_BREAKS = {1: 0.0, 5: disc_5, 10: disc_10, 25: disc_25, 50: disc_50}

st.divider()

# ── Cost engine ───────────────────────────────────────────────────────────────
def _calc_steps(n_units: int) -> tuple[float, float, float, list[dict]]:
    """Returns (total_proc, total_machine, total_labour, per_step_list)."""
    total_proc = total_mach = total_lab = 0.0
    details: list[dict] = []
    for _, row in steps_df.iterrows():
        m_rate = float(row.get("machine_rate_eur_h", 90.0))
        l_rate = float(row.get("labor_rate_eur_h",  58.0))
        sc     = float(row.get("subcon_eur", 0.0))
        rt     = float(row.get("runtime_h",  0.0))
        su     = float(row.get("setup_h",    0.0))
        pid    = str(row.get("process_id",   ""))

        if sc > 0:
            step_mach = 0.0
            step_lab  = 0.0
            step_proc = sc
        else:
            eff_h     = rt + su / max(n_units, 1)
            step_mach = eff_h * m_rate
            step_lab  = eff_h * l_rate
            step_proc = step_mach + step_lab

        total_proc += step_proc
        total_mach += step_mach
        total_lab  += step_lab
        details.append({
            "process_id": pid,
            "runtime_h":  rt,
            "setup_h":    su,
            "machine_c":  step_mach,
            "labour_c":   step_lab,
            "proc_cost":  step_proc,
            "subcon":     sc > 0,
        })
    return total_proc, total_mach, total_lab, details


def _cost_per_unit(n_units: int, mat_discount: float = 0.0) -> dict:
    eff_price_kg = price_kg * (1 - mat_discount)
    mat_c        = purchase_mass * eff_price_kg

    total_proc, total_mach, total_lab, step_details = _calc_steps(n_units)

    # NDT at average blended rate across steps
    if steps_df.empty:
        blended_rate = 75.0
    else:
        avg_m = steps_df["machine_rate_eur_h"].mean()
        avg_l = steps_df["labor_rate_eur_h"].mean()
        blended_rate = (avg_m + avg_l) / 2

    ndt_cost  = ndt_h * blended_rate
    surf_cost = SURFACE_TREATMENTS[surface]["cost_eur"]
    overhead  = total_proc * overhead_pct
    base      = mat_c + total_proc + ndt_cost + surf_cost + overhead
    cert_sc   = base * CERT_SURCHARGES[cert_class]
    frt_unit  = freight_eur / max(n_units, 1)
    base_full = base + cert_sc + frt_unit
    margin    = base_full * margin_pct
    sell      = base_full + margin

    return {
        "n_units":      n_units,
        "mat":          mat_c,
        "process":      total_proc,
        "machine":      total_mach,
        "labour":       total_lab,
        "step_details": step_details,
        "ndt":          ndt_cost,
        "surface":      surf_cost,
        "overhead":     overhead,
        "cert_sc":      cert_sc,
        "freight":      frt_unit,
        "base":         base_full,
        "margin":       margin,
        "sell":         sell,
        "mat_discount": mat_discount,
    }


# Base calculation (at entered qty)
c = _cost_per_unit(qty_base)

# ── Cost waterfall KPIs ───────────────────────────────────────────────────────
st.subheader("Cost build-up")

w1, w2, w3, w4, w5, w6 = st.columns(6)
w1.metric("Material (purchase)",   fmt(c["mat"], 2))
w2.metric("Process (all steps)",   fmt(c["process"], 2))
w3.metric("Overhead",              fmt(c["overhead"], 2))
w4.metric("Surcharges",            fmt(c["ndt"] + c["surface"] + c["cert_sc"] + c["freight"], 2))
w5.metric("Your cost",             fmt(c["base"], 2))
w6.metric("Sell price / unit",     fmt(c["sell"], 2),
          delta=f"Margin {fmt(c['margin'], 2)} ({margin_pct*100:.1f}%)")

st.divider()

# ── Visual cost stack ─────────────────────────────────────────────────────────
stack_data = pd.DataFrame([{
    "Material":  c["mat"],
    "Process":   c["process"],
    "Overhead":  c["overhead"],
    "Surcharge": c["ndt"] + c["surface"] + c["cert_sc"] + c["freight"],
    "Margin":    c["margin"],
}], index=[part_name])

col_chart, col_pct = st.columns([2, 1])
with col_chart:
    st.caption("Cost composition — stacked bar")
    st.bar_chart(stack_data, color=["#2196F3", "#FF9800", "#9C27B0", "#F44336", "#4CAF50"])

total_sell = c["sell"]
with col_pct:
    pct_df = pd.DataFrame({
        "Element": ["Material", "Process", "Overhead", "Surcharge", "Margin"],
        "€":       [c["mat"], c["process"], c["overhead"],
                    c["ndt"] + c["surface"] + c["cert_sc"] + c["freight"],
                    c["margin"]],
    })
    pct_df["% of sell"] = (pct_df["€"] / total_sell * 100).round(1)
    pct_df["€"]         = pct_df["€"].map(lambda x: fmt(x, 2))
    pct_df["% of sell"] = pct_df["% of sell"].map(lambda x: f"{x:.1f}%")
    st.dataframe(pct_df, use_container_width=True, hide_index=True)

st.divider()

# ── Full line breakdown ───────────────────────────────────────────────────────
with st.expander("Full cost line detail", expanded=True):
    rows: list[tuple[str, str, str]] = [
        ("Purchase mass",     f"{purchase_mass:.3f} kg",  ""),
        ("Material rate",     f"{fmt(price_kg, 2)}/kg",   ""),
        ("Material cost",     fmt(c["mat"], 2),            ""),
    ]

    # Per-step process costs
    for i, sd in enumerate(c["step_details"], 1):
        label = f"  Op {i}: {sd['process_id']}"
        if sd["subcon"]:
            rows.append((label, fmt(sd["proc_cost"], 2), "subcontract"))
        else:
            amort_su = sd["setup_h"] / max(qty_base, 1)
            rows.append((label,
                         fmt(sd["proc_cost"], 2),
                         f"{sd['runtime_h']:.2f}h run + {amort_su:.3f}h setup"))

    rows += [
        ("Process cost (total)",    fmt(c["process"], 2),  f"{len(c['step_details'])} operations"),
        ("NDT cost",                fmt(c["ndt"], 2),       f"{ndt_h:.1f} h" if ndt_h else "not applicable"),
        ("Surface treatment",       fmt(c["surface"], 2),   surface if surface != "None" else "none"),
        ("Overhead",                fmt(c["overhead"], 2),  f"{overhead_pct*100:.1f}% of process"),
        ("Certification surcharge", fmt(c["cert_sc"], 2),   f"{CERT_SURCHARGES[cert_class]*100:.0f}% of base"
                                                             if cert_class != "None" else "not applicable"),
        ("Freight / packing",       fmt(c["freight"], 2),   f"€{freight_eur:.0f} ÷ {qty_base} units" if freight_eur else "not applicable"),
        ("Your cost (base)",        fmt(c["base"], 2),      ""),
        ("Margin",                  fmt(c["margin"], 2),    f"{margin_pct*100:.1f}% of base"),
        ("Sell price / unit",       fmt(c["sell"], 2),      ""),
        ("Total order value",       fmt(c["sell"] * qty_base, 2), f"× {qty_base} units"),
    ]
    detail_df = pd.DataFrame(rows, columns=["Element", "Value", "Note"])
    st.dataframe(detail_df, use_container_width=True, hide_index=True)

st.divider()

# ── Volume discount table ─────────────────────────────────────────────────────
st.subheader("Volume pricing")
st.caption("Setup time amortised + material discount applied at each break.")

vol_rows: list[dict] = []
for n, disc in sorted(VOLUME_BREAKS.items()):
    cv = _cost_per_unit(n, disc)
    vol_rows.append({**cv, "_n": n, "_disc": disc})

base_sell = vol_rows[0]["sell"]
display_rows = []
for r in vol_rows:
    display_rows.append({
        "Qty":           r["_n"],
        "Mat. discount": f"{r['_disc']*100:.1f}%",
        "Material €":    fmt(r["mat"], 2),
        "Process €":     fmt(r["process"], 2),
        "Overhead €":    fmt(r["overhead"], 2),
        "Your cost €":   fmt(r["base"], 2),
        "Sell / unit €": fmt(r["sell"], 2),
        "Total order €": fmt(r["sell"] * r["_n"], 2),
        "vs qty 1":      fmt_delta(r["sell"] - base_sell, 2) if r["sell"] != base_sell else "—",
    })

display_vol = pd.DataFrame(display_rows)

def _highlight(row):
    if int(row["Qty"]) == qty_base:
        return ["background-color: #1a3a5c"] * len(row)
    return [""] * len(row)

st.dataframe(
    display_vol.style.apply(_highlight, axis=1),
    use_container_width=True, hide_index=True,
)

# Volume sell price chart
chart_rows = []
for n, disc in sorted(VOLUME_BREAKS.items()):
    chart_rows.append({"Qty (units)": str(n), "Sell price / unit (€)": _cost_per_unit(n, disc)["sell"]})
chart_df = pd.DataFrame(chart_rows).set_index("Qty (units)")
st.bar_chart(chart_df)

st.divider()

# ── Download ──────────────────────────────────────────────────────────────────
st.subheader("Download")

export_detail = pd.DataFrame(rows, columns=["Element", "Value", "Note"])
export_vol    = display_vol.copy()

# Routing sheet
routing_export = steps_df.copy()

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    export_detail.to_excel(w, sheet_name="Cost Breakdown", index=False)
    export_vol.to_excel(w, sheet_name="Volume Pricing", index=False)
    routing_export.to_excel(w, sheet_name="Process Routing", index=False)

st.download_button(
    f"⬇️ Download costing — {part_name} (Excel)",
    data=buf.getvalue(),
    file_name=f"item_costing_{part_name.lower().replace(' ', '_')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
