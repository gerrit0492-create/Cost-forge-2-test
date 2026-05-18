"""BOM Import & Calculatie — upload een BOM CSV en bereken direct alle kosten."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.docx_export import make_offer_docx
from utils.io import load_materials, load_processes, load_quotes
from utils.pdf_export import make_offer_pdf
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.safe import guard

BOM_PATH = Path("data/bom.csv")

REQUIRED_COLS = ["line_id", "material_id", "qty", "mass_kg", "process_route", "runtime_h"]

DISPLAY_COLS = [
    "line_id", "material_id", "qty", "mass_kg",
    "price_eur_per_kg", "material_cost",
    "process_route", "runtime_h", "process_cost",
    "overhead", "margin", "total_cost",
]

_TEMPLATE = pd.DataFrame([
    # Staal
    dict(line_id="L01", material_id="S235",       qty=1,  mass_kg=8.50, process_route="LASER_CUT",    runtime_h=0.45),
    dict(line_id="L02", material_id="S235",       qty=2,  mass_kg=3.20, process_route="BENDING",       runtime_h=0.30),
    dict(line_id="L03", material_id="S355",       qty=4,  mass_kg=1.80, process_route="LASER_CUT",     runtime_h=0.20),
    dict(line_id="L04", material_id="S235",       qty=1,  mass_kg=0.00, process_route="MIG_WELD",      runtime_h=2.50),
    # Aluminium
    dict(line_id="L05", material_id="AL6061",     qty=1,  mass_kg=4.20, process_route="CNC_MILL_5AX",  runtime_h=3.50),
    dict(line_id="L06", material_id="AL6061",     qty=2,  mass_kg=1.60, process_route="CNC_MILL_3AX",  runtime_h=1.20),
    dict(line_id="L07", material_id="AL5083",     qty=1,  mass_kg=2.40, process_route="WATERJET",      runtime_h=0.60),
    dict(line_id="L08", material_id="AL6061",     qty=4,  mass_kg=0.30, process_route="ANODIZE",       runtime_h=0.25),
    # Roestvast staal
    dict(line_id="L09", material_id="316",        qty=2,  mass_kg=0.90, process_route="CNC_LATHE",     runtime_h=0.80),
    dict(line_id="L10", material_id="316",        qty=1,  mass_kg=2.10, process_route="CNC_MILL_3AX",  runtime_h=1.40),
    dict(line_id="L11", material_id="304",        qty=1,  mass_kg=0.95, process_route="CNC_LATHE",     runtime_h=0.55),
    dict(line_id="L12", material_id="1.4462",     qty=1,  mass_kg=3.80, process_route="TIG_WELD",      runtime_h=2.20),
    # Titanium
    dict(line_id="L13", material_id="Ti6Al4V",   qty=1,  mass_kg=0.65, process_route="3DP_SLM",       runtime_h=4.50),
    # Gietijzer
    dict(line_id="L14", material_id="EN-GJS-500", qty=2,  mass_kg=2.80, process_route="CNC_LATHE",     runtime_h=1.60),
    dict(line_id="L15", material_id="EN-GJL-250", qty=1,  mass_kg=5.20, process_route="CNC_MILL_3AX",  runtime_h=1.80),
    dict(line_id="L16", material_id="EN-GJS-500", qty=2,  mass_kg=3.10, process_route="GRIND_SURF",    runtime_h=0.90),
    # Kunststof
    dict(line_id="L17", material_id="POM",        qty=8,  mass_kg=0.12, process_route="CNC_LATHE",     runtime_h=0.25),
    dict(line_id="L18", material_id="PTFE",       qty=4,  mass_kg=0.05, process_route="CNC_LATHE",     runtime_h=0.15),
    dict(line_id="L19", material_id="PA6",        qty=6,  mass_kg=0.18, process_route="CNC_MILL_3AX",  runtime_h=0.20),
    dict(line_id="L20", material_id="POM",        qty=12, mass_kg=0.08, process_route="DRILL_TAP",     runtime_h=0.12),
    # Koper / Messing
    dict(line_id="L21", material_id="CuETP",      qty=3,  mass_kg=0.35, process_route="CNC_LATHE",     runtime_h=0.40),
    dict(line_id="L22", material_id="CuZn37",     qty=6,  mass_kg=0.22, process_route="CNC_LATHE",     runtime_h=0.35),
    # Afwerking & montage
    dict(line_id="L23", material_id="S235",       qty=1,  mass_kg=6.20, process_route="PAINT",         runtime_h=0.50),
    dict(line_id="L24", material_id="AL6061",     qty=2,  mass_kg=0.50, process_route="3DP_FDM",       runtime_h=1.20),
    dict(line_id="L25", material_id="S235",       qty=1,  mass_kg=0.00, process_route="ASSEMBLY",      runtime_h=4.00),
])


def _metric_row(df: pd.DataFrame) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Materiaalkosten",  f"EUR {df['material_cost'].sum():,.2f}")
    c2.metric("Bewerkingskosten", f"EUR {df['process_cost'].sum():,.2f}")
    c3.metric("Overhead",         f"EUR {df['overhead'].sum():,.2f}")
    c4.metric("Marge",            f"EUR {df['margin'].sum():,.2f}")
    c5.metric("**TOTAAL**",       f"EUR {df['total_cost'].sum():,.2f}")


def main() -> None:
    st.title("📥 BOM Import & Calculatie")
    st.caption(
        "Upload een BOM CSV met de vereiste kolommen. "
        "Kosten worden direct berekend op basis van de materialen- en bewerkingsdatabase."
    )

    # ── Template download — always visible at the top ────────────────────────
    st.subheader("Stap 1 — Download het template")
    st.markdown(
        "Het template bevat alle beschikbare **material_id**'s en **process_route**'s als voorbeeldregels. "
        "Pas de waarden aan voor jouw project en upload het bestand hieronder."
    )
    col_dl, col_info = st.columns([1, 3])
    col_dl.download_button(
        label="⬇️  Download BOM template (.csv)",
        data=_TEMPLATE.to_csv(index=False).encode(),
        file_name="bom_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    col_info.markdown(
        "**Vereiste kolommen:**  "
        "`line_id` · `material_id` · `qty` · `mass_kg` · `process_route` · `runtime_h`  \n"
        "_mass\\_kg = 0 is toegestaan (bijv. lassen of montage zonder materiaalgewicht)_"
    )

    # ── Reference tables ─────────────────────────────────────────────────────
    mats   = load_materials()
    procs  = load_processes()
    quotes = load_quotes()

    c1, c2 = st.columns(2)
    with c1.expander("📋 Beschikbare materialen"):
        st.dataframe(
            mats[["material_id", "description", "price_eur_per_kg"]],
            use_container_width=True, hide_index=True,
        )
    with c2.expander("⚙️ Beschikbare bewerkingen"):
        st.dataframe(
            procs[["process_id", "description", "machine_rate_eur_h", "labor_rate_eur_h", "overhead_pct", "margin_pct"]],
            use_container_width=True, hide_index=True,
        )

    # ── Upload ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Stap 2 — Upload jouw ingevulde BOM")
    up = st.file_uploader("📂 Sleep het bestand hierheen of klik om te bladeren", type=["csv"])
    if not up:
        st.info("Upload een BOM CSV om te beginnen.")
        return

    try:
        bom = pd.read_csv(up)
    except Exception as e:
        st.error(f"CSV kon niet worden gelezen: {e}")
        return

    st.subheader("Ingelezen BOM")
    st.dataframe(bom, use_container_width=True, hide_index=True)

    # ── Validate columns ──────────────────────────────────────────────────────
    missing_cols = [c for c in REQUIRED_COLS if c not in bom.columns]
    if missing_cols:
        st.error(f"❌ Ontbrekende kolommen: `{'`, `'.join(missing_cols)}`")
        st.info(f"Vereiste kolommen: `{'`, `'.join(REQUIRED_COLS)}`")
        return

    # Cast numeric columns
    for col in ["qty", "mass_kg", "runtime_h"]:
        bom[col] = pd.to_numeric(bom[col], errors="coerce").fillna(0)
    bom["qty"] = bom["qty"].astype("Int64")

    # ── Validate material_ids ─────────────────────────────────────────────────
    known_mats  = set(mats["material_id"])
    unknown_mats = sorted(set(bom["material_id"].astype(str)) - known_mats)

    # ── Validate process_routes ───────────────────────────────────────────────
    known_procs   = set(procs["process_id"])
    unknown_procs = sorted(set(bom["process_route"].astype(str)) - known_procs)

    has_errors = False
    if unknown_mats:
        st.error(
            f"❌ Onbekende material_id's (geen prijs beschikbaar): "
            f"`{'`, `'.join(unknown_mats)}`\n\n"
            "Voeg ze toe aan de materiaaldatabase of pas de BOM aan."
        )
        has_errors = True
    if unknown_procs:
        st.error(
            f"❌ Onbekende process_route's: "
            f"`{'`, `'.join(unknown_procs)}`\n\n"
            "Voeg ze toe aan de procesdatabase of pas de BOM aan."
        )
        has_errors = True
    if has_errors:
        return

    st.success(f"✅ Validatie geslaagd — {len(bom)} regels, alle materialen en bewerkingen bekend.")

    # ── Calculate costs ───────────────────────────────────────────────────────
    mats_q = apply_best_quotes(mats, quotes)
    try:
        df = compute_costs(mats_q, procs, bom)
    except ValueError as e:
        st.error(f"Berekening mislukt: {e}")
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.subheader("💶 Kostenoverzicht")
    _metric_row(df)

    # ── Cost breakdown by material group ──────────────────────────────────────
    if "commodity" in df.columns:
        grp = (
            df.groupby("commodity", dropna=False)[
                ["material_cost", "process_cost", "overhead", "margin", "total_cost"]
            ]
            .sum()
            .sort_values("total_cost", ascending=False)
            .round(2)
        )
        with st.expander("📊 Kosten per materiaalgroep"):
            st.dataframe(grp, use_container_width=True)

    # ── Line-by-line detail ───────────────────────────────────────────────────
    st.subheader("📋 Regeldetail")
    avail_cols = [c for c in DISPLAY_COLS if c in df.columns]
    st.dataframe(
        df[avail_cols].round(4),
        use_container_width=True,
        hide_index=True,
    )

    # ── Save BOM so other pages use it ───────────────────────────────────────
    BOM_PATH.write_text(bom.to_csv(index=False), encoding="utf-8")
    st.caption(f"BOM opgeslagen als `{BOM_PATH}` — alle andere pagina's gebruiken nu deze BOM.")

    # ── Exports ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("⬇️ Exporteer resultaten")
    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "CSV — volledige calculatie",
        df[avail_cols].round(4).to_csv(index=False).encode(),
        file_name="calculatie.csv",
        mime="text/csv",
    )
    e2.download_button(
        "DOCX — offerte",
        make_offer_docx(df),
        file_name="offerte.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    e3.download_button(
        "PDF — offerte",
        make_offer_pdf(df),
        file_name="offerte.pdf",
        mime="application/pdf",
    )


guard(main)
