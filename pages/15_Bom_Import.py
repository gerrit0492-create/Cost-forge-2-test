"""BOM Import & Calculation — upload a BOM CSV and calculate all costs immediately."""

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
from utils.nav import home_button
from utils.project import load_project_name, save_project_name

BOM_PATH = Path("data/bom.csv")

REQUIRED_COLS = ["line_id", "material_id", "qty", "mass_kg", "process_route", "runtime_h"]

DISPLAY_COLS = [
    "line_id",
    "material_id",
    "qty",
    "mass_kg",
    "price_eur_per_kg",
    "material_cost",
    "process_route",
    "runtime_h",
    "process_cost",
    "overhead",
    "margin",
    "total_cost",
]

_TEMPLATE = pd.DataFrame(
    [
        # ── Impeller Assembly ─────────────────────────────────────────────
        dict(line_id="I01", material_id="NAB",       qty=1, mass_kg=45.0,  process_route="5AX_MILL_IMP",   runtime_h=36.0),
        dict(line_id="I02", material_id="NAB",       qty=1, mass_kg=10.5,  process_route="5AX_MILL_IMP",   runtime_h=5.5),
        dict(line_id="I03", material_id="NAB",       qty=1, mass_kg=6.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="I04", material_id="SS316L",    qty=1, mass_kg=4.8,   process_route="CNC_MILL_3AX",   runtime_h=2.5),
        dict(line_id="I05", material_id="NAB",       qty=1, mass_kg=4.0,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="I06", material_id="SS316L",    qty=1, mass_kg=2.5,   process_route="CNC_MILL_3AX",   runtime_h=1.5),
        dict(line_id="I07", material_id="SS316L",    qty=4, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="I08", material_id="NAB",       qty=1, mass_kg=1.6,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="I09", material_id="SS174PH",   qty=1, mass_kg=0.6,   process_route="CNC_LATHE_PREC", runtime_h=0.8),
        dict(line_id="I10", material_id="SS316L",    qty=6, mass_kg=0.15,  process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="I11", material_id="NAB",       qty=1, mass_kg=4.5,   process_route="SURF_GRIND",     runtime_h=2.5),
        dict(line_id="I12", material_id="NAB",       qty=1, mass_kg=3.0,   process_route="SURF_GRIND",     runtime_h=1.5),
        dict(line_id="I13", material_id="SS316L",    qty=1, mass_kg=1.2,   process_route="CNC_MILL_3AX",   runtime_h=0.8),
        dict(line_id="I14", material_id="NR_RUBBER", qty=2, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="I15", material_id="A4_FAST",   qty=1, mass_kg=1.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="I16", material_id="SS316L",    qty=1, mass_kg=0.8,   process_route="CNC_MILL_3AX",   runtime_h=0.5),
        dict(line_id="I17", material_id="HDPE",      qty=2, mass_kg=0.5,   process_route="WATERJET_CUT",   runtime_h=0.3),
        dict(line_id="I18", material_id="SS316L",    qty=1, mass_kg=0.6,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="I19", material_id="NAB",       qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=2.5),
        dict(line_id="I20", material_id="NAB",       qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=1.5),
        # ── Pump Housing Assembly ─────────────────────────────────────────
        dict(line_id="H01", material_id="NAB_CAST",  qty=1, mass_kg=120.0, process_route="SAND_CAST",      runtime_h=65.0),
        dict(line_id="H02", material_id="NAB_CAST",  qty=1, mass_kg=35.0,  process_route="SAND_CAST",      runtime_h=25.0),
        dict(line_id="H03", material_id="SS316L",    qty=1, mass_kg=25.0,  process_route="PREC_BORE",      runtime_h=12.0),
        dict(line_id="H04", material_id="SS316L",    qty=1, mass_kg=18.0,  process_route="CNC_MILL_3AX",   runtime_h=6.5),
        dict(line_id="H05", material_id="SS316L",    qty=1, mass_kg=15.0,  process_route="CNC_MILL_3AX",   runtime_h=5.0),
        dict(line_id="H06", material_id="SS316L",    qty=2, mass_kg=8.5,   process_route="CNC_MILL_3AX",   runtime_h=3.5),
        dict(line_id="H07", material_id="SS316L",    qty=1, mass_kg=7.0,   process_route="TIG_WELD_316",   runtime_h=3.0),
        dict(line_id="H08", material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="TIG_WELD_316",   runtime_h=5.0),
        dict(line_id="H09", material_id="SS316L",    qty=2, mass_kg=5.5,   process_route="TIG_WELD_316",   runtime_h=2.5),
        dict(line_id="H10", material_id="SS316L",    qty=1, mass_kg=4.5,   process_route="PREC_BORE",      runtime_h=2.0),
        dict(line_id="H11", material_id="SS316L",    qty=1, mass_kg=3.8,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="H12", material_id="SS2205",    qty=1, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=3.0),
        dict(line_id="H13", material_id="SS2205",    qty=1, mass_kg=6.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="H14", material_id="SS316L",    qty=4, mass_kg=2.2,   process_route="CNC_MILL_3AX",   runtime_h=1.0),
        dict(line_id="H15", material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="PLASMA_CUT",     runtime_h=1.5),
        dict(line_id="H16", material_id="SS316L",    qty=2, mass_kg=3.5,   process_route="PLASMA_CUT",     runtime_h=0.8),
        dict(line_id="H17", material_id="A4_FAST",   qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="H18", material_id="SS316L",    qty=1, mass_kg=1.8,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="H19", material_id="NR_RUBBER", qty=1, mass_kg=2.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="H20", material_id="HDPE",      qty=2, mass_kg=1.2,   process_route="CNC_MILL_3AX",   runtime_h=0.6),
        dict(line_id="H21", material_id="SS316L",    qty=1, mass_kg=2.8,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="H22", material_id="SS316L",    qty=6, mass_kg=0.5,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="H23", material_id="SS316L",    qty=1, mass_kg=1.5,   process_route="CNC_MILL_3AX",   runtime_h=0.8),
        dict(line_id="H24", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=3.0),
        dict(line_id="H25", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=3.0),
        # ── Shaft Line ────────────────────────────────────────────────────
        dict(line_id="S01", material_id="SS174PH",   qty=1, mass_kg=55.0,  process_route="CNC_LATHE_PREC", runtime_h=22.0),
        dict(line_id="S02", material_id="SS174PH",   qty=1, mass_kg=14.0,  process_route="CNC_LATHE_PREC", runtime_h=7.0),
        dict(line_id="S03", material_id="SS174PH",   qty=1, mass_kg=9.5,   process_route="CNC_LATHE_PREC", runtime_h=5.0),
        dict(line_id="S04", material_id="SS174PH",   qty=1, mass_kg=6.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="S05", material_id="SS174PH",   qty=1, mass_kg=4.8,   process_route="SURF_GRIND",     runtime_h=3.0),
        dict(line_id="S06", material_id="SS174PH",   qty=1, mass_kg=3.8,   process_route="SURF_GRIND",     runtime_h=2.5),
        dict(line_id="S07", material_id="SS316L",    qty=2, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="S08", material_id="SS316L",    qty=2, mass_kg=6.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="S09", material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="PREC_BORE",      runtime_h=2.5),
        dict(line_id="S10", material_id="SS316L",    qty=2, mass_kg=4.2,   process_route="PREC_BORE",      runtime_h=2.0),
        dict(line_id="S11", material_id="SS316L",    qty=1, mass_kg=3.5,   process_route="CNC_MILL_3AX",   runtime_h=2.0),
        dict(line_id="S12", material_id="CUNI90",    qty=1, mass_kg=4.5,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="S13", material_id="CUNI90",    qty=1, mass_kg=3.2,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="S14", material_id="SS316L",    qty=1, mass_kg=2.8,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="S15", material_id="SS316L",    qty=2, mass_kg=1.5,   process_route="CNC_MILL_3AX",   runtime_h=0.8),
        dict(line_id="S16", material_id="SS174PH",   qty=1, mass_kg=2.2,   process_route="HARD_CHROME",    runtime_h=1.5),
        dict(line_id="S17", material_id="SS174PH",   qty=1, mass_kg=1.8,   process_route="HARD_CHROME",    runtime_h=1.0),
        dict(line_id="S18", material_id="HDPE",      qty=2, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="S19", material_id="NR_RUBBER", qty=4, mass_kg=0.4,   process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="S20", material_id="SS316L",    qty=6, mass_kg=0.3,   process_route="CNC_LATHE_PREC", runtime_h=0.2),
        dict(line_id="S21", material_id="A4_FAST",   qty=1, mass_kg=2.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="S22", material_id="SS316L",    qty=1, mass_kg=1.2,   process_route="CNC_LATHE_PREC", runtime_h=0.6),
        dict(line_id="S23", material_id="SS316L",    qty=1, mass_kg=0.8,   process_route="CNC_MILL_3AX",   runtime_h=0.4),
        dict(line_id="S24", material_id="CUNI90",    qty=2, mass_kg=0.6,   process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="S25", material_id="NR_RUBBER", qty=2, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="S26", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=2.0),
        dict(line_id="S27", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="SURF_GRIND",     runtime_h=1.5),
        dict(line_id="S28", material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=2.0),
        dict(line_id="S29", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.0),
        dict(line_id="S30", material_id="A4_FAST",   qty=1, mass_kg=1.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        # ── Inlet Duct Assembly ───────────────────────────────────────────
        dict(line_id="D01", material_id="SS316L",    qty=1, mass_kg=45.0,  process_route="TIG_WELD_316",   runtime_h=12.0),
        dict(line_id="D02", material_id="SS316L",    qty=1, mass_kg=28.0,  process_route="TIG_WELD_316",   runtime_h=8.0),
        dict(line_id="D03", material_id="SS316L",    qty=1, mass_kg=18.0,  process_route="CNC_MILL_3AX",   runtime_h=5.0),
        dict(line_id="D04", material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="CNC_MILL_3AX",   runtime_h=4.0),
        dict(line_id="D05", material_id="SS316L",    qty=2, mass_kg=8.0,   process_route="TIG_WELD_316",   runtime_h=3.0),
        dict(line_id="D06", material_id="SS316L",    qty=1, mass_kg=6.5,   process_route="PLASMA_CUT",     runtime_h=2.0),
        dict(line_id="D07", material_id="SS316L",    qty=2, mass_kg=5.5,   process_route="PLASMA_CUT",     runtime_h=1.5),
        dict(line_id="D08", material_id="SS316L",    qty=1, mass_kg=4.5,   process_route="CNC_MILL_3AX",   runtime_h=2.0),
        dict(line_id="D09", material_id="S355J2",    qty=1, mass_kg=8.5,   process_route="TIG_WELD_316",   runtime_h=3.5),
        dict(line_id="D10", material_id="S355J2",    qty=1, mass_kg=6.2,   process_route="PLASMA_CUT",     runtime_h=1.5),
        dict(line_id="D11", material_id="HDPE",      qty=2, mass_kg=2.5,   process_route="WATERJET_CUT",   runtime_h=0.8),
        dict(line_id="D12", material_id="SS316L",    qty=1, mass_kg=3.2,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="D13", material_id="NR_RUBBER", qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="D14", material_id="SS316L",    qty=4, mass_kg=1.2,   process_route="CNC_LATHE_PREC", runtime_h=0.6),
        dict(line_id="D15", material_id="A4_FAST",   qty=1, mass_kg=2.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="D16", material_id="SS316L",    qty=2, mass_kg=2.5,   process_route="CNC_MILL_3AX",   runtime_h=1.2),
        dict(line_id="D17", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=4.0),
        dict(line_id="D18", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.0),
        dict(line_id="D19", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=1.5),
        dict(line_id="D20", material_id="SS316L",    qty=6, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        # ── Jet Nozzle Assembly ───────────────────────────────────────────
        dict(line_id="N01", material_id="SS316L",    qty=1, mass_kg=22.0,  process_route="CNC_LATHE_PREC", runtime_h=6.0),
        dict(line_id="N02", material_id="SS316L",    qty=1, mass_kg=15.0,  process_route="CNC_MILL_3AX",   runtime_h=4.0),
        dict(line_id="N03", material_id="SS2205",    qty=1, mass_kg=12.0,  process_route="CNC_LATHE_PREC", runtime_h=4.5),
        dict(line_id="N04", material_id="SS316L",    qty=1, mass_kg=8.5,   process_route="CNC_MILL_3AX",   runtime_h=3.0),
        dict(line_id="N05", material_id="NAB",       qty=1, mass_kg=6.2,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="N06", material_id="SS316L",    qty=1, mass_kg=4.8,   process_route="PREC_BORE",      runtime_h=2.0),
        dict(line_id="N07", material_id="SS316L",    qty=2, mass_kg=3.5,   process_route="TIG_WELD_316",   runtime_h=1.5),
        dict(line_id="N08", material_id="HDPE",      qty=2, mass_kg=1.5,   process_route="WATERJET_CUT",   runtime_h=0.5),
        dict(line_id="N09", material_id="SS316L",    qty=4, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="N10", material_id="NR_RUBBER", qty=2, mass_kg=0.4,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="N11", material_id="A4_FAST",   qty=1, mass_kg=2.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="N12", material_id="SS316L",    qty=1, mass_kg=1.8,   process_route="CNC_LATHE_PREC", runtime_h=0.8),
        dict(line_id="N13", material_id="SS316L",    qty=6, mass_kg=0.4,   process_route="CNC_LATHE_PREC", runtime_h=0.2),
        dict(line_id="N14", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=1.5),
        dict(line_id="N15", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=2.0),
        # ── Steering System ───────────────────────────────────────────────
        dict(line_id="ST01", material_id="SS316L",   qty=1, mass_kg=18.0,  process_route="CNC_MILL_3AX",   runtime_h=5.0),
        dict(line_id="ST02", material_id="SS316L",   qty=1, mass_kg=12.0,  process_route="CNC_MILL_3AX",   runtime_h=4.0),
        dict(line_id="ST03", material_id="SS316L",   qty=2, mass_kg=8.0,   process_route="CNC_LATHE_PREC", runtime_h=3.0),
        dict(line_id="ST04", material_id="SS316L",   qty=1, mass_kg=6.5,   process_route="TIG_WELD_316",   runtime_h=2.5),
        dict(line_id="ST05", material_id="SS316L",   qty=1, mass_kg=5.2,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="ST06", material_id="SS316L",   qty=2, mass_kg=4.5,   process_route="CNC_MILL_3AX",   runtime_h=2.0),
        dict(line_id="ST07", material_id="SS316L",   qty=1, mass_kg=3.8,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="ST08", material_id="SS316L",   qty=2, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.2),
        dict(line_id="ST09", material_id="SS316L",   qty=1, mass_kg=4.5,   process_route="PREC_BORE",      runtime_h=2.0),
        dict(line_id="ST10", material_id="SS316L",   qty=2, mass_kg=3.2,   process_route="PREC_BORE",      runtime_h=1.5),
        dict(line_id="ST11", material_id="AL6082",   qty=2, mass_kg=2.8,   process_route="CNC_MILL_3AX",   runtime_h=1.5),
        dict(line_id="ST12", material_id="AL6082",   qty=2, mass_kg=1.5,   process_route="CNC_MILL_3AX",   runtime_h=0.8),
        dict(line_id="ST13", material_id="SS316L",   qty=4, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="ST14", material_id="SS316L",   qty=1, mass_kg=2.8,   process_route="TIG_WELD_316",   runtime_h=1.5),
        dict(line_id="ST15", material_id="SS316L",   qty=1, mass_kg=1.5,   process_route="CNC_LATHE_PREC", runtime_h=0.8),
        dict(line_id="ST16", material_id="SS316L",   qty=2, mass_kg=0.8,   process_route="CNC_MILL_3AX",   runtime_h=0.4),
        dict(line_id="ST17", material_id="HDPE",     qty=2, mass_kg=0.8,   process_route="WATERJET_CUT",   runtime_h=0.3),
        dict(line_id="ST18", material_id="NR_RUBBER",qty=4, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="ST19", material_id="A4_FAST",  qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="ST20", material_id="SS316L",   qty=1, mass_kg=1.2,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="ST21", material_id="SS316L",   qty=6, mass_kg=0.3,   process_route="CNC_LATHE_PREC", runtime_h=0.15),
        dict(line_id="ST22", material_id="AL6082",   qty=2, mass_kg=0.5,   process_route="ANODIZE",        runtime_h=1.0),
        dict(line_id="ST23", material_id="SS316L",   qty=1, mass_kg=0.5,   process_route="CNC_MILL_3AX",   runtime_h=0.3),
        dict(line_id="ST24", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=1.0),
        dict(line_id="ST25", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=1.5),
        # ── Reverse System ────────────────────────────────────────────────
        dict(line_id="R01", material_id="SS316L",    qty=1, mass_kg=22.0,  process_route="CNC_MILL_3AX",   runtime_h=6.0),
        dict(line_id="R02", material_id="SS316L",    qty=1, mass_kg=15.0,  process_route="TIG_WELD_316",   runtime_h=5.0),
        dict(line_id="R03", material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="CNC_MILL_3AX",   runtime_h=4.0),
        dict(line_id="R04", material_id="SS316L",    qty=2, mass_kg=8.0,   process_route="CNC_LATHE_PREC", runtime_h=3.0),
        dict(line_id="R05", material_id="SS316L",    qty=1, mass_kg=6.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="R06", material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="TIG_WELD_316",   runtime_h=2.5),
        dict(line_id="R07", material_id="SS316L",    qty=2, mass_kg=4.5,   process_route="CNC_MILL_3AX",   runtime_h=2.0),
        dict(line_id="R08", material_id="SS316L",    qty=1, mass_kg=3.8,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="R09", material_id="SS316L",    qty=2, mass_kg=2.5,   process_route="TIG_WELD_316",   runtime_h=1.5),
        dict(line_id="R10", material_id="AL6082",    qty=2, mass_kg=2.2,   process_route="CNC_MILL_3AX",   runtime_h=1.2),
        dict(line_id="R11", material_id="SS316L",    qty=4, mass_kg=1.2,   process_route="CNC_LATHE_PREC", runtime_h=0.6),
        dict(line_id="R12", material_id="SS316L",    qty=1, mass_kg=3.2,   process_route="PREC_BORE",      runtime_h=1.5),
        dict(line_id="R13", material_id="SS316L",    qty=1, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.2),
        dict(line_id="R14", material_id="SS316L",    qty=6, mass_kg=0.5,   process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="R15", material_id="NR_RUBBER", qty=4, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="R16", material_id="A4_FAST",   qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="R17", material_id="SS316L",    qty=1, mass_kg=1.2,   process_route="CNC_MILL_3AX",   runtime_h=0.5),
        dict(line_id="R18", material_id="HDPE",      qty=2, mass_kg=0.8,   process_route="WATERJET_CUT",   runtime_h=0.3),
        dict(line_id="R19", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=3.0),
        dict(line_id="R20", material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.0),
        # ── Mounting Frame ────────────────────────────────────────────────
        dict(line_id="F01", material_id="S355J2",    qty=1, mass_kg=85.0,  process_route="TIG_WELD_316",   runtime_h=18.0),
        dict(line_id="F02", material_id="S355J2",    qty=1, mass_kg=45.0,  process_route="TIG_WELD_316",   runtime_h=10.0),
        dict(line_id="F03", material_id="S355J2",    qty=1, mass_kg=35.0,  process_route="PLASMA_CUT",     runtime_h=3.0),
        dict(line_id="F04", material_id="S355J2",    qty=1, mass_kg=28.0,  process_route="PLASMA_CUT",     runtime_h=2.5),
        dict(line_id="F05", material_id="S355J2",    qty=2, mass_kg=15.0,  process_route="TIG_WELD_316",   runtime_h=4.0),
        dict(line_id="F06", material_id="S355J2",    qty=1, mass_kg=12.0,  process_route="PLASMA_CUT",     runtime_h=1.5),
        dict(line_id="F07", material_id="S355J2",    qty=4, mass_kg=8.0,   process_route="PLASMA_CUT",     runtime_h=1.0),
        dict(line_id="F08", material_id="S355J2",    qty=2, mass_kg=6.5,   process_route="TIG_WELD_316",   runtime_h=2.0),
        dict(line_id="F09", material_id="AL6082",    qty=2, mass_kg=4.5,   process_route="CNC_MILL_3AX",   runtime_h=2.0),
        dict(line_id="F10", material_id="AL6082",    qty=4, mass_kg=1.8,   process_route="CNC_MILL_3AX",   runtime_h=1.0),
        dict(line_id="F11", material_id="S355J2",    qty=8, mass_kg=0.8,   process_route="PLASMA_CUT",     runtime_h=0.4),
        dict(line_id="F12", material_id="A4_FAST",   qty=1, mass_kg=5.0,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="F13", material_id="SS316L",    qty=1, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="F14", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=6.0),
        dict(line_id="F15", material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=2.0),
        # ── Sealing System ────────────────────────────────────────────────
        dict(line_id="SE01", material_id="SS316L",   qty=1, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="SE02", material_id="SS316L",   qty=1, mass_kg=6.2,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="SE03", material_id="NR_RUBBER",qty=2, mass_kg=1.5,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="SE04", material_id="NR_RUBBER",qty=4, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="SE05", material_id="PEEK",     qty=2, mass_kg=0.3,   process_route="CNC_LATHE_PREC", runtime_h=0.8),
        dict(line_id="SE06", material_id="PEEK",     qty=4, mass_kg=0.15,  process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="SE07", material_id="SS316L",   qty=2, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="SE08", material_id="SS316L",   qty=4, mass_kg=1.2,   process_route="CNC_LATHE_PREC", runtime_h=0.6),
        dict(line_id="SE09", material_id="CUNI90",   qty=2, mass_kg=1.8,   process_route="CNC_LATHE_PREC", runtime_h=0.8),
        dict(line_id="SE10", material_id="SS316L",   qty=1, mass_kg=2.5,   process_route="PREC_BORE",      runtime_h=1.0),
        dict(line_id="SE11", material_id="SS316L",   qty=1, mass_kg=1.8,   process_route="PREC_BORE",      runtime_h=0.8),
        dict(line_id="SE12", material_id="A4_FAST",  qty=1, mass_kg=1.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="SE13", material_id="SS316L",   qty=1, mass_kg=1.2,   process_route="CNC_MILL_3AX",   runtime_h=0.5),
        dict(line_id="SE14", material_id="NR_RUBBER",qty=1, mass_kg=0.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="SE15", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=1.0),
        # ── Hydraulic System ──────────────────────────────────────────────
        dict(line_id="HY01", material_id="SS316L_TUBE", qty=1, mass_kg=4.5, process_route="TIG_WELD_316",  runtime_h=3.0),
        dict(line_id="HY02", material_id="SS316L_TUBE", qty=1, mass_kg=3.2, process_route="TIG_WELD_316",  runtime_h=2.5),
        dict(line_id="HY03", material_id="SS316L",   qty=1, mass_kg=5.5,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="HY04", material_id="SS316L",   qty=2, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="HY05", material_id="SS316L_TUBE", qty=4, mass_kg=0.8, process_route="TIG_WELD_316",  runtime_h=0.5),
        dict(line_id="HY06", material_id="SS316L",   qty=2, mass_kg=1.5,   process_route="CNC_MILL_3AX",   runtime_h=0.6),
        dict(line_id="HY07", material_id="NR_RUBBER",qty=8, mass_kg=0.1,   process_route="FINAL_ASSEMBLY", runtime_h=0.1),
        dict(line_id="HY08", material_id="A4_FAST",  qty=1, mass_kg=1.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HY09", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.0),
        dict(line_id="HY10", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=1.0),
        # ── Fasteners & Hardware ──────────────────────────────────────────
        dict(line_id="HW01", material_id="A4_FAST",  qty=1, mass_kg=8.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="HW02", material_id="A4_FAST",  qty=1, mass_kg=5.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="HW03", material_id="A4_FAST",  qty=1, mass_kg=4.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HW04", material_id="A4_FAST",  qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HW05", material_id="A4_FAST",  qty=1, mass_kg=2.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HW06", material_id="SS316L",   qty=1, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="HW07", material_id="SS316L",   qty=2, mass_kg=1.5,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="HW08", material_id="SS316L",   qty=4, mass_kg=0.5,   process_route="CNC_LATHE_PREC", runtime_h=0.2),
        dict(line_id="HW09", material_id="A4_FAST",  qty=1, mass_kg=1.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.1),
        dict(line_id="HW10", material_id="NR_RUBBER",qty=1, mass_kg=0.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.1),
        # ── QA / Testing / Inspection ─────────────────────────────────────
        dict(line_id="QA01", material_id="NAB",      qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=3.0),
        dict(line_id="QA02", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=2.0),
        dict(line_id="QA03", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=4.0),
        dict(line_id="QA04", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=8.0),
        dict(line_id="QA05", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=3.0),
        dict(line_id="QA06", material_id="SS174PH",  qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=4.0),
        dict(line_id="QA07", material_id="NAB_CAST", qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=5.0),
        dict(line_id="QA08", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="FINAL_ASSEMBLY", runtime_h=24.0),
        dict(line_id="QA09", material_id="SS316L",   qty=1, mass_kg=0.0,   process_route="FINAL_ASSEMBLY", runtime_h=12.0),
    ]
)


def _metric_row(df: pd.DataFrame) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Material cost", f"EUR {df['material_cost'].sum():,.2f}")
    c2.metric("Process cost", f"EUR {df['process_cost'].sum():,.2f}")
    c3.metric("Overhead", f"EUR {df['overhead'].sum():,.2f}")
    c4.metric("Margin", f"EUR {df['margin'].sum():,.2f}")
    c5.metric("**TOTAL**", f"EUR {df['total_cost'].sum():,.2f}")


def main() -> None:
    home_button()
    st.title("📥 BOM Import & Calculation")
    st.caption(
        "Upload a BOM CSV with the required columns. "
        "Costs are calculated immediately based on the materials and processes database."
    )

    # ── Assembly / project name ───────────────────────────────────────────────
    current_name = load_project_name()
    name_col, _ = st.columns([2, 3])
    new_name = name_col.text_input("🏷️ Assembly / Project name", value=current_name,
                                   placeholder="e.g. Marine Waterjet MWJ-720")
    if new_name != current_name:
        save_project_name(new_name)
        st.success(f"Assembly name saved: **{new_name}**")

    st.divider()

    # ── Template download — always visible at the top ────────────────────────
    st.subheader("Step 1 — Download the template")
    st.markdown(
        "The template contains a complete 214-line **MWJ-720 marine waterjet BOM** as an example. "
        "Adjust the values for your project and upload the file below."
    )
    col_dl, col_info = st.columns([1, 3])
    col_dl.download_button(
        label="⬇️  Download BOM template (.csv)",
        data=_TEMPLATE.to_csv(index=False).encode(),
        file_name="bom_template_mwj720.csv",
        mime="text/csv",
        use_container_width=True,
    )
    col_info.markdown(
        "**Required columns:**  "
        "`line_id` · `material_id` · `qty` · `mass_kg` · `process_route` · `runtime_h`  \n"
        "_mass\\_kg = 0 is allowed (e.g. dynamic balancing, pressure testing or final assembly without net material weight)_  \n"
        "**Marine materials** (e.g. `NAB`, `SS316L`, `SS2205`, `SS174PH`, `AL6082`, `S355J2`, `HDPE`, `NR_RUBBER`, `PEEK`, `CUNI90`) · "
        "**Marine processes** (e.g. `5AX_MILL_IMP`, `CNC_LATHE_PREC`, `TIG_WELD_316`, `SAND_CAST`, `DYN_BALANCE`, `NDT_INSPECT`, `FINAL_ASSEMBLY`)"
    )

    # ── Reference tables ─────────────────────────────────────────────────────
    mats = load_materials()
    procs = load_processes()
    quotes = load_quotes()

    c1, c2 = st.columns(2)
    with c1.expander("📋 Available materials"):
        st.dataframe(
            mats[["material_id", "description", "price_eur_per_kg"]],
            use_container_width=True,
            hide_index=True,
        )
    with c2.expander("⚙️ Available processes"):
        st.dataframe(
            procs[
                [
                    "process_id",
                    "description",
                    "machine_rate_eur_h",
                    "labor_rate_eur_h",
                    "overhead_pct",
                    "margin_pct",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    # ── Upload ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Step 2 — Upload your completed BOM")
    up = st.file_uploader("📂 Drag the file here or click to browse", type=["csv"])
    if not up:
        st.info("Upload a BOM CSV to get started.")
        return

    try:
        bom = pd.read_csv(up)
    except Exception as e:
        st.error(f"CSV could not be read: {e}")
        return

    st.subheader("Imported BOM")
    st.dataframe(bom, use_container_width=True, hide_index=True)

    # ── Validate columns ──────────────────────────────────────────────────────
    missing_cols = [c for c in REQUIRED_COLS if c not in bom.columns]
    if missing_cols:
        st.error(f"❌ Missing columns: `{'`, `'.join(missing_cols)}`")
        st.info(f"Required columns: `{'`, `'.join(REQUIRED_COLS)}`")
        return

    # Cast numeric columns
    for col in ["qty", "mass_kg", "runtime_h"]:
        bom[col] = pd.to_numeric(bom[col], errors="coerce").fillna(0)
    bom["qty"] = bom["qty"].astype("Int64")

    # ── Validate material_ids ─────────────────────────────────────────────────
    known_mats = set(mats["material_id"])
    unknown_mats = sorted(set(bom["material_id"].astype(str)) - known_mats)

    # ── Validate process_routes ───────────────────────────────────────────────
    known_procs = set(procs["process_id"])
    unknown_procs = sorted(set(bom["process_route"].astype(str)) - known_procs)

    has_errors = False
    if unknown_mats:
        st.error(
            f"❌ Unknown material_id's (no price available): "
            f"`{'`, `'.join(unknown_mats)}`\n\n"
            "Add them to the materials database or adjust the BOM."
        )
        has_errors = True
    if unknown_procs:
        st.error(
            f"❌ Unknown process_route's: "
            f"`{'`, `'.join(unknown_procs)}`\n\n"
            "Add them to the processes database or adjust the BOM."
        )
        has_errors = True
    if has_errors:
        return

    st.success(f"✅ Validation passed — {len(bom)} lines, all materials and processes known.")

    # ── Calculate costs ───────────────────────────────────────────────────────
    mats_q = apply_best_quotes(mats, quotes)
    try:
        df = compute_costs(mats_q, procs, bom)
    except ValueError as e:
        st.error(f"Calculation failed: {e}")
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.subheader("💶 Cost overview")
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
        with st.expander("📊 Costs per material group"):
            st.dataframe(grp, use_container_width=True)

    # ── Line-by-line detail ───────────────────────────────────────────────────
    st.subheader("📋 Line detail")
    avail_cols = [c for c in DISPLAY_COLS if c in df.columns]
    st.dataframe(
        df[avail_cols].round(4),
        use_container_width=True,
        hide_index=True,
    )

    # ── Save BOM so other pages use it ───────────────────────────────────────
    BOM_PATH.write_text(bom.to_csv(index=False), encoding="utf-8")
    st.caption(f"BOM saved as `{BOM_PATH}` — all other pages now use this BOM.")

    # ── Exports ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("⬇️ Export results")
    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "CSV — full calculation",
        df[avail_cols].round(4).to_csv(index=False).encode(),
        file_name="calculation.csv",
        mime="text/csv",
    )
    e2.download_button(
        "DOCX — quote",
        make_offer_docx(df),
        file_name="quote.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    e3.download_button(
        "PDF — quote",
        make_offer_pdf(df),
        file_name="quote.pdf",
        mime="application/pdf",
    )


guard(main)
