"""BOM Import & Calculation — upload a BOM CSV and calculate all costs immediately."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from utils.completeness import (
    WATERJET_SUBSYSTEMS,
    common_missing,
    completeness_score,
    detect_subsystems,
    record_bom_load,
)
from utils.docx_export import make_offer_docx
from utils.io import load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.pdf_export import make_offer_pdf
from utils.pricing import compute_costs
from utils.project import load_project_name, save_project_name
from utils.quotes import apply_best_quotes
from utils.safe import guard

BOM_PATH = Path("data/bom.csv")

REQUIRED_COLS = ["line_id", "material_id", "qty", "mass_kg", "process_route", "runtime_h"]

DISPLAY_COLS = [
    "line_id",
    "part_name",
    "material_id",
    "qty",
    "mass_kg",
    "yield_factor",
    "price_eur_per_kg",
    "material_cost",
    "process_route",
    "runtime_h",
    "setup_h",
    "machine_cost",
    "labour_cost",
    "process_cost",
    "overhead",
    "base_cost",
    "margin",
    "total_cost",
]

_TEMPLATE = pd.DataFrame(
    [
        # ── Impeller Assembly (I) — 5-blade NAB OD720 ─────────────────────
        dict(line_id="I01",  part_name="5-blade impeller body OD720 NAB billet-machined", material_id="NAB",       qty=1, mass_kg=68.0,  process_route="5AX_MILL_IMP",   runtime_h=44.0),
        dict(line_id="I02",  part_name="Impeller back ring / balance ring NAB",            material_id="NAB",       qty=1, mass_kg=9.2,   process_route="CNC_LATHE_PREC", runtime_h=4.0),
        dict(line_id="I03",  part_name="Front wear ring OD720 NAB",                        material_id="NAB",       qty=1, mass_kg=7.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="I04",  part_name="Rear wear ring NAB",                               material_id="NAB",       qty=1, mass_kg=6.2,   process_route="CNC_LATHE_PREC", runtime_h=3.0),
        dict(line_id="I05",  part_name="Shaft seal carrier SS316L",                        material_id="SS316L",    qty=1, mass_kg=4.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="I06",  part_name="Impeller retaining nut 17-4PH",                    material_id="SS174PH",   qty=1, mass_kg=2.8,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="I07",  part_name="Wear insert set SS2205 (4-off)",                   material_id="SS2205",    qty=4, mass_kg=0.9,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="I08",  part_name="Lip seals & O-ring kit NBR",                       material_id="NR_RUBBER", qty=1, mass_kg=1.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="I09",  part_name="Impeller fastener kit A4-80 M20-M30",              material_id="A4_FAST",   qty=1, mass_kg=2.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="I10",  part_name="Dynamic balance G2.5 finished impeller",           material_id="NAB",       qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=4.0),
        dict(line_id="I11",  part_name="NDT dye-pen + UT blade inspection",                material_id="NAB",       qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=3.0),
        dict(line_id="I12",  part_name="Impeller assembly & shaft fit-check",              material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="FINAL_ASSEMBLY", runtime_h=4.0),
        # ── Stator Bowl (SB) — cast NAB diffuser OD850 ────────────────────
        dict(line_id="SB01", part_name="Diffuser stator casting NAB OD850",                material_id="NAB_CAST",  qty=1, mass_kg=108.0, process_route="SAND_CAST",      runtime_h=56.0),
        dict(line_id="SB02", part_name="Stator vane set 7-off machined NAB",               material_id="NAB",       qty=1, mass_kg=34.0,  process_route="5AX_MILL_IMP",   runtime_h=20.0),
        dict(line_id="SB03", part_name="Diffuser inner bore & flow passages",              material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="PREC_BORE",      runtime_h=7.0),
        dict(line_id="SB04", part_name="Discharge transition ring SS2205",                 material_id="SS2205",    qty=1, mass_kg=14.0,  process_route="CNC_LATHE_PREC", runtime_h=4.5),
        dict(line_id="SB05", part_name="Stator inner sleeve NAB",                          material_id="NAB",       qty=1, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=4.0),
        dict(line_id="SB06", part_name="Stator seal ring pair NBR",                        material_id="NR_RUBBER", qty=2, mass_kg=0.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="SB07", part_name="Stator stud & nut set A4-80",                      material_id="A4_FAST",   qty=1, mass_kg=4.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="SB08", part_name="Stator wear liner pair HDPE",                      material_id="HDPE",      qty=2, mass_kg=3.0,   process_route="WATERJET_CUT",   runtime_h=0.8),
        dict(line_id="SB09", part_name="NDT casting dye-pen + radiography",                material_id="NAB_CAST",  qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=4.5),
        dict(line_id="SB10", part_name="Hydraulic pressure test 15 bar",                   material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=3.0),
        # ── Pump Housing (H) — main volute NAB_CAST OD960 ─────────────────
        dict(line_id="H01",  part_name="Main volute casting NAB OD960",                    material_id="NAB_CAST",  qty=1, mass_kg=168.0, process_route="SAND_CAST",      runtime_h=72.0),
        dict(line_id="H02",  part_name="Volute front cover casting NAB",                   material_id="NAB_CAST",  qty=1, mass_kg=44.0,  process_route="SAND_CAST",      runtime_h=28.0),
        dict(line_id="H03",  part_name="Bearing housing machined SS2205",                  material_id="SS2205",    qty=1, mass_kg=36.0,  process_route="CNC_LATHE_PREC", runtime_h=12.0),
        dict(line_id="H04",  part_name="Volute precision bore & face machining",           material_id="NAB_CAST",  qty=1, mass_kg=0.0,   process_route="PREC_BORE",      runtime_h=14.0),
        dict(line_id="H05",  part_name="Discharge flange 316L machined",                   material_id="SS316L",    qty=1, mass_kg=18.0,  process_route="CNC_MILL_3AX",   runtime_h=5.5),
        dict(line_id="H06",  part_name="Inlet suction port 316L machined",                 material_id="SS316L",    qty=1, mass_kg=15.0,  process_route="CNC_MILL_3AX",   runtime_h=4.5),
        dict(line_id="H07",  part_name="Front bearing carrier 316L bored",                 material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="PREC_BORE",      runtime_h=4.0),
        dict(line_id="H08",  part_name="Rear bearing carrier 316L bored",                  material_id="SS316L",    qty=1, mass_kg=9.5,   process_route="PREC_BORE",      runtime_h=3.5),
        dict(line_id="H09",  part_name="Drain & vent fittings SS316L (2-off)",             material_id="SS316L",    qty=2, mass_kg=3.8,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="H10",  part_name="Housing O-ring & gasket set NBR",                  material_id="NR_RUBBER", qty=1, mass_kg=3.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="H11",  part_name="Housing stud bolt set A4-80 M30",                  material_id="A4_FAST",   qty=1, mass_kg=5.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="H12",  part_name="NDT casting + bore inspection",                    material_id="NAB_CAST",  qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=6.0),
        dict(line_id="H13",  part_name="Assembled housing pressure test 12 bar",           material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=4.0),
        # ── Shaft Line (S) — 17-4PH main shaft Ø140 L=1850 ──────────────
        dict(line_id="S01",  part_name="Main drive shaft 17-4PH Ø140 L=1850",             material_id="SS174PH",   qty=1, mass_kg=72.0,  process_route="CNC_LATHE_PREC", runtime_h=26.0),
        dict(line_id="S02",  part_name="Forward journal cylindrical grind",                material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="SURF_GRIND",     runtime_h=3.5),
        dict(line_id="S03",  part_name="Engine-side coupling half 17-4PH",                 material_id="SS174PH",   qty=1, mass_kg=18.5,  process_route="CNC_LATHE_PREC", runtime_h=7.0),
        dict(line_id="S04",  part_name="Impeller-side coupling hub 17-4PH",                material_id="SS174PH",   qty=1, mass_kg=14.0,  process_route="CNC_LATHE_PREC", runtime_h=5.5),
        dict(line_id="S05",  part_name="Intermediate shaft sleeve 17-4PH",                 material_id="SS174PH",   qty=1, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=4.0),
        dict(line_id="S06",  part_name="Bearing journal sleeve 17-4PH ground",             material_id="SS174PH",   qty=1, mass_kg=5.5,   process_route="SURF_GRIND",     runtime_h=3.0),
        dict(line_id="S07",  part_name="Angular contact bearing inner ring (2-off)",       material_id="SS316L",    qty=2, mass_kg=5.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="S08",  part_name="Thrust bearing race pair SS316L",                  material_id="SS316L",    qty=2, mass_kg=4.2,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="S09",  part_name="Shaft locking nut & tab washer 17-4PH",            material_id="SS174PH",   qty=1, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="S10",  part_name="Hard chrome journals 2 zones",                     material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="HARD_CHROME",    runtime_h=3.5),
        dict(line_id="S11",  part_name="Shaft lip seal set NBR (4-off)",                   material_id="NR_RUBBER", qty=4, mass_kg=0.4,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="S12",  part_name="Shaft fastener kit A4-80",                         material_id="A4_FAST",   qty=1, mass_kg=2.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.4),
        dict(line_id="S13",  part_name="Dynamic balance assembled shaft",                  material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=3.5),
        dict(line_id="S14",  part_name="NDT UT + MPI shaft inspection",                    material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=4.5),
        # ── Thrust Block (TB) — SS2205 duplex Ø380 ───────────────────────
        dict(line_id="TB01", part_name="Thrust housing body SS2205 Ø380",                  material_id="SS2205",    qty=1, mass_kg=52.0,  process_route="CNC_LATHE_PREC", runtime_h=14.0),
        dict(line_id="TB02", part_name="Thrust collar SS2205 Ø280 precision",              material_id="SS2205",    qty=1, mass_kg=22.0,  process_route="PREC_BORE",      runtime_h=9.0),
        dict(line_id="TB03", part_name="Thrust pad carrier 17-4PH",                        material_id="SS174PH",   qty=1, mass_kg=12.0,  process_route="CNC_LATHE_PREC", runtime_h=5.5),
        dict(line_id="TB04", part_name="Thrust bearing face precision grind",              material_id="SS2205",    qty=1, mass_kg=0.0,   process_route="PREC_BORE",      runtime_h=4.0),
        dict(line_id="TB05", part_name="Thrust pads CuNi90/10 (2-off)",                    material_id="CUNI90",    qty=2, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="TB06", part_name="Seal carrier SS316L",                              material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="CNC_LATHE_PREC", runtime_h=2.5),
        dict(line_id="TB07", part_name="O-ring & seal kit NBR",                            material_id="NR_RUBBER", qty=4, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="TB08", part_name="Thrust block fastener kit A4-80",                  material_id="A4_FAST",   qty=1, mass_kg=3.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.4),
        dict(line_id="TB09", part_name="NDT inspection thrust housing",                    material_id="SS2205",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=3.5),
        dict(line_id="TB10", part_name="Pressure test assembled block 20 bar",             material_id="SS2205",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.5),
        # ── Inlet Duct (D) — 316L TIG-welded duct ────────────────────────
        dict(line_id="D01",  part_name="Main inlet duct shell 316L TIG welded",            material_id="SS316L",    qty=1, mass_kg=58.0,  process_route="TIG_WELD_316",   runtime_h=14.0),
        dict(line_id="D02",  part_name="Duct inlet flange 316L machined",                  material_id="SS316L",    qty=1, mass_kg=22.0,  process_route="CNC_MILL_3AX",   runtime_h=6.0),
        dict(line_id="D03",  part_name="Hull mounting flange 316L",                        material_id="SS316L",    qty=1, mass_kg=18.0,  process_route="CNC_MILL_3AX",   runtime_h=5.0),
        dict(line_id="D04",  part_name="Intake grating bar assembly 316L",                 material_id="SS316L",    qty=1, mass_kg=12.0,  process_route="TIG_WELD_316",   runtime_h=4.0),
        dict(line_id="D05",  part_name="Inspection port cover (2-off) 316L",               material_id="SS316L",    qty=2, mass_kg=6.5,   process_route="CNC_MILL_3AX",   runtime_h=2.5),
        dict(line_id="D06",  part_name="Anti-cavitation lip profile 316L",                 material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="WATERJET_CUT",   runtime_h=2.0),
        dict(line_id="D07",  part_name="Hull backing plate S355J2",                        material_id="S355J2",    qty=1, mass_kg=8.5,   process_route="PLASMA_CUT",     runtime_h=1.5),
        dict(line_id="D08",  part_name="Rubber transition boot NBR",                       material_id="NR_RUBBER", qty=1, mass_kg=4.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.8),
        dict(line_id="D09",  part_name="Duct fastener kit A4-80",                          material_id="A4_FAST",   qty=1, mass_kg=3.2,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="D10",  part_name="Weld seam NDT + dimensional survey",               material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=3.0),
        dict(line_id="D11",  part_name="Pressure test flow passage 8 bar",                 material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=2.5),
        # ── Jet Nozzle (N) — 316L nozzle body OD720 ──────────────────────
        dict(line_id="N01",  part_name="Nozzle body 316L OD720 machined",                  material_id="SS316L",    qty=1, mass_kg=28.0,  process_route="CNC_LATHE_PREC", runtime_h=7.5),
        dict(line_id="N02",  part_name="Nozzle exit wear ring SS2205",                     material_id="SS2205",    qty=1, mass_kg=14.0,  process_route="CNC_LATHE_PREC", runtime_h=5.0),
        dict(line_id="N03",  part_name="Steering pivot housing 316L",                      material_id="SS316L",    qty=1, mass_kg=10.5,  process_route="CNC_MILL_3AX",   runtime_h=4.0),
        dict(line_id="N04",  part_name="Nozzle inner liner SS2205",                        material_id="SS2205",    qty=1, mass_kg=8.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="N05",  part_name="Deflector hinge pin 316L (2-off)",                 material_id="SS316L",    qty=2, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="N06",  part_name="Nozzle seal & O-ring set NBR",                     material_id="NR_RUBBER", qty=2, mass_kg=0.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="N07",  part_name="Nozzle fastener kit A4-80",                        material_id="A4_FAST",   qty=1, mass_kg=2.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="N08",  part_name="Nozzle dimensional check & seal test",             material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=1.5),
        dict(line_id="N09",  part_name="NDT nozzle body inspection",                       material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=1.5),
        # ── Steering System (ST) — tiller plates + pivot ──────────────────
        dict(line_id="ST01", part_name="Steering tiller plate port 316L",                  material_id="SS316L",    qty=1, mass_kg=14.0,  process_route="CNC_MILL_3AX",   runtime_h=5.5),
        dict(line_id="ST02", part_name="Steering tiller plate stbd 316L",                  material_id="SS316L",    qty=1, mass_kg=14.0,  process_route="CNC_MILL_3AX",   runtime_h=5.5),
        dict(line_id="ST03", part_name="Steering pivot shaft 316L Ø80",                    material_id="SS316L",    qty=1, mass_kg=10.5,  process_route="CNC_LATHE_PREC", runtime_h=4.0),
        dict(line_id="ST04", part_name="Actuator bracket weldment 316L",                   material_id="SS316L",    qty=1, mass_kg=8.5,   process_route="TIG_WELD_316",   runtime_h=3.5),
        dict(line_id="ST05", part_name="Steering arm pair 316L",                           material_id="SS316L",    qty=2, mass_kg=5.5,   process_route="CNC_MILL_3AX",   runtime_h=2.5),
        dict(line_id="ST06", part_name="Pivot bearing housing 316L bored",                 material_id="SS316L",    qty=1, mass_kg=5.0,   process_route="PREC_BORE",      runtime_h=2.5),
        dict(line_id="ST07", part_name="Tiller clevis & pin set 316L",                     material_id="SS316L",    qty=2, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="ST08", part_name="CuNi90/10 pivot bush pair",                        material_id="CUNI90",    qty=2, mass_kg=1.8,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="ST09", part_name="Seal & protection boot set NBR",                   material_id="NR_RUBBER", qty=4, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="ST10", part_name="Steering fastener kit A4-80",                      material_id="A4_FAST",   qty=1, mass_kg=4.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.4),
        # ── Reverse System (R) — thrust reverser bucket ───────────────────
        dict(line_id="R01",  part_name="Reverse bucket body 316L machined",                material_id="SS316L",    qty=1, mass_kg=28.0,  process_route="CNC_MILL_3AX",   runtime_h=7.0),
        dict(line_id="R02",  part_name="Bucket shell weldment 316L",                       material_id="SS316L",    qty=1, mass_kg=18.0,  process_route="TIG_WELD_316",   runtime_h=5.5),
        dict(line_id="R03",  part_name="Hinge shaft 316L Ø60",                             material_id="SS316L",    qty=1, mass_kg=10.5,  process_route="CNC_LATHE_PREC", runtime_h=4.5),
        dict(line_id="R04",  part_name="Actuator bracket pair 316L",                       material_id="SS316L",    qty=2, mass_kg=6.5,   process_route="CNC_MILL_3AX",   runtime_h=2.5),
        dict(line_id="R05",  part_name="Bucket guide rail 316L",                           material_id="SS316L",    qty=1, mass_kg=5.5,   process_route="CNC_MILL_3AX",   runtime_h=2.5),
        dict(line_id="R06",  part_name="Hinge pin pair 316L (2-off)",                      material_id="SS316L",    qty=2, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="R07",  part_name="CuNi90/10 hinge bush pair",                        material_id="CUNI90",    qty=2, mass_kg=2.0,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="R08",  part_name="Seal & protection boot set NBR",                   material_id="NR_RUBBER", qty=4, mass_kg=0.3,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="R09",  part_name="Reverse fastener kit A4-80",                       material_id="A4_FAST",   qty=1, mass_kg=4.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.4),
        dict(line_id="R10",  part_name="Powder coat bucket interior",                      material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=3.5),
        # ── Mounting Frame (F) — S355J2 welded baseframe ──────────────────
        dict(line_id="F01",  part_name="Main baseframe weldment S355J2",                   material_id="S355J2",    qty=1, mass_kg=95.0,  process_route="TIG_WELD_316",   runtime_h=22.0),
        dict(line_id="F02",  part_name="Cross-member set S355J2 (4-off)",                  material_id="S355J2",    qty=4, mass_kg=18.0,  process_route="TIG_WELD_316",   runtime_h=4.5),
        dict(line_id="F03",  part_name="Hull mounting pad set S355J2 (6-off)",             material_id="S355J2",    qty=6, mass_kg=5.5,   process_route="PLASMA_CUT",     runtime_h=0.8),
        dict(line_id="F04",  part_name="Alignment plate set S355J2 (4-off)",               material_id="S355J2",    qty=4, mass_kg=4.5,   process_route="CNC_MILL_3AX",   runtime_h=1.5),
        dict(line_id="F05",  part_name="Stiffener plate set S355J2",                       material_id="S355J2",    qty=1, mass_kg=22.0,  process_route="PLASMA_CUT",     runtime_h=2.0),
        dict(line_id="F06",  part_name="Vibration mount bracket S355J2 (4-off)",           material_id="S355J2",    qty=4, mass_kg=3.5,   process_route="PLASMA_CUT",     runtime_h=0.5),
        dict(line_id="F07",  part_name="Frame fastener & anchor kit A4-80",                material_id="A4_FAST",   qty=1, mass_kg=6.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="F08",  part_name="Sand blast + 2-coat marine epoxy",                 material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="POWDER_COAT",    runtime_h=8.0),
        dict(line_id="F09",  part_name="Weld seam NDT frame",                              material_id="S355J2",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=3.0),
        # ── Sealing System (SE) — shaft seals ────────────────────────────
        dict(line_id="SE01", part_name="Shaft face seal housing 316L",                     material_id="SS316L",    qty=1, mass_kg=9.5,   process_route="CNC_LATHE_PREC", runtime_h=4.0),
        dict(line_id="SE02", part_name="Mechanical seal carrier 316L",                     material_id="SS316L",    qty=1, mass_kg=7.5,   process_route="CNC_LATHE_PREC", runtime_h=3.5),
        dict(line_id="SE03", part_name="Seal housing precision bore",                      material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PREC_BORE",      runtime_h=2.5),
        dict(line_id="SE04", part_name="PEEK bush set OD50 (4-off)",                       material_id="PEEK",      qty=4, mass_kg=0.18,  process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="SE05", part_name="Primary lip seal pair NBR",                        material_id="NR_RUBBER", qty=2, mass_kg=0.8,   process_route="CNC_LATHE_PREC", runtime_h=0.4),
        dict(line_id="SE06", part_name="Secondary O-ring backup kit",                      material_id="NR_RUBBER", qty=4, mass_kg=0.4,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="SE07", part_name="Water lube port fitting 316L",                     material_id="SS316L",    qty=1, mass_kg=2.5,   process_route="CNC_LATHE_PREC", runtime_h=1.5),
        dict(line_id="SE08", part_name="Seal gland follower 316L",                         material_id="SS316L",    qty=1, mass_kg=2.2,   process_route="CNC_LATHE_PREC", runtime_h=1.2),
        dict(line_id="SE09", part_name="Seal fastener kit A4-80",                          material_id="A4_FAST",   qty=1, mass_kg=1.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="SE10", part_name="Seal assembly pressure test",                      material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=1.5),
        # ── Hydraulic System (HY) — 316L manifold + tube ─────────────────
        dict(line_id="HY01", part_name="Hydraulic manifold block 316L machined",           material_id="SS316L",    qty=1, mass_kg=6.5,   process_route="CNC_MILL_3AX",   runtime_h=4.5),
        dict(line_id="HY02", part_name="Steering cylinder supply tube 316L",               material_id="SS316L_TUBE",qty=1, mass_kg=3.8,  process_route="TIG_WELD_316",   runtime_h=2.5),
        dict(line_id="HY03", part_name="Reverse cylinder supply tube 316L",                material_id="SS316L_TUBE",qty=1, mass_kg=3.5,  process_route="TIG_WELD_316",   runtime_h=2.5),
        dict(line_id="HY04", part_name="Return line tube set 316L (3-off)",                material_id="SS316L_TUBE",qty=3, mass_kg=1.5,  process_route="TIG_WELD_316",   runtime_h=1.0),
        dict(line_id="HY05", part_name="Pressure relief valve body 316L",                  material_id="SS316L",    qty=1, mass_kg=2.8,   process_route="CNC_LATHE_PREC", runtime_h=2.0),
        dict(line_id="HY06", part_name="Tube fitting set machined 316L (12-off)",          material_id="SS316L",    qty=12, mass_kg=0.15, process_route="CNC_LATHE_PREC", runtime_h=0.3),
        dict(line_id="HY07", part_name="O-ring & seal kit hydraulic NBR",                  material_id="NR_RUBBER", qty=1, mass_kg=0.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HY08", part_name="Hydraulic system flush & pressure test",           material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=3.0),
        dict(line_id="HY09", part_name="NDT weld inspection hydraulic",                    material_id="SS316L_TUBE",qty=1, mass_kg=0.0,  process_route="NDT_INSPECT",    runtime_h=1.5),
        # ── Fasteners & Hardware (HW) — A4-80 sets ───────────────────────
        dict(line_id="HW01", part_name="M30 stud & nut set housing bolting",               material_id="A4_FAST",   qty=1, mass_kg=9.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.6),
        dict(line_id="HW02", part_name="M24 stud & nut set impeller side",                 material_id="A4_FAST",   qty=1, mass_kg=7.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.5),
        dict(line_id="HW03", part_name="M20 cap screw set cover plates",                   material_id="A4_FAST",   qty=1, mass_kg=5.5,   process_route="FINAL_ASSEMBLY", runtime_h=0.4),
        dict(line_id="HW04", part_name="M16 socket head screw set general",                material_id="A4_FAST",   qty=1, mass_kg=4.0,   process_route="FINAL_ASSEMBLY", runtime_h=0.3),
        dict(line_id="HW05", part_name="M12 fastener set brackets & clips",                material_id="A4_FAST",   qty=1, mass_kg=2.8,   process_route="FINAL_ASSEMBLY", runtime_h=0.2),
        dict(line_id="HW06", part_name="Pin & retaining ring set 316L",                    material_id="SS316L",    qty=1, mass_kg=3.5,   process_route="CNC_LATHE_PREC", runtime_h=1.0),
        dict(line_id="HW07", part_name="Lifting eye bolt set 316L (4-off)",                material_id="SS316L",    qty=4, mass_kg=1.8,   process_route="CNC_LATHE_PREC", runtime_h=0.5),
        dict(line_id="HW08", part_name="Rating plate & name plate 316L",                   material_id="SS316L",    qty=1, mass_kg=0.5,   process_route="CNC_MILL_3AX",   runtime_h=0.5),
        # ── QA / Testing (QA) — final acceptance ─────────────────────────
        dict(line_id="QA01", part_name="Dynamic balance impeller G2.5 final",              material_id="NAB",       qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=5.0),
        dict(line_id="QA02", part_name="Dynamic balance complete rotor",                   material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="DYN_BALANCE",    runtime_h=4.0),
        dict(line_id="QA03", part_name="Unit hydrostatic pressure test",                   material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=6.0),
        dict(line_id="QA04", part_name="Flow performance acceptance test",                 material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="PRESSURE_TEST",  runtime_h=12.0),
        dict(line_id="QA05", part_name="Final dimensional survey + NDT",                   material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=8.0),
        dict(line_id="QA06", part_name="Shaft + impeller MPI/UT inspection",               material_id="SS174PH",   qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=5.0),
        dict(line_id="QA07", part_name="Casting radiography x-ray (3 castings)",           material_id="NAB_CAST",  qty=1, mass_kg=0.0,   process_route="NDT_INSPECT",    runtime_h=7.0),
        dict(line_id="QA08", part_name="Final assembly alignment & FAT",                   material_id="SS316L",    qty=1, mass_kg=0.0,   process_route="FINAL_ASSEMBLY", runtime_h=32.0),
    ]
)

# ── Enrich template with optional columns ─────────────────────────────────────
_SETUP_H: dict[str, float] = {
    "I01": 8.0, "SB01": 8.0, "SB02": 6.0, "SB03": 2.0,
    "H01": 12.0, "H02": 8.0, "H03": 3.0, "H04": 4.0,
    "H05": 2.0, "H06": 2.0, "H07": 2.0, "H08": 2.0,
    "S01": 4.0, "S02": 2.0, "S03": 3.0, "S04": 2.5, "S05": 1.5, "S06": 2.0,
    "S07": 1.5, "S08": 1.5, "S09": 1.0, "S10": 2.0,
    "TB01": 3.0, "TB02": 3.0, "TB03": 2.0, "TB04": 2.0,
    "D01": 4.0, "D02": 2.0, "D03": 2.0, "D04": 2.0,
    "N01": 2.5, "N02": 2.0,
    "ST01": 2.0, "ST02": 2.0, "ST03": 2.0, "ST04": 2.0,
    "R01": 2.5, "R02": 2.0,
    "F01": 5.0, "F02": 3.0,
    "SE01": 2.0, "SE02": 2.0, "SE03": 2.0,
    "HY01": 2.0, "QA08": 4.0,
}
_YIELD_BY_PROCESS: dict[str, float] = {
    "SAND_CAST": 0.60, "TIG_WELD_316": 0.90, "PLASMA_CUT": 0.85,
}
_TEMPLATE["setup_h"]              = _TEMPLATE["line_id"].map(_SETUP_H).fillna(0.0)
_TEMPLATE["yield_factor"]         = _TEMPLATE["process_route"].map(_YIELD_BY_PROCESS).fillna(1.0)
_TEMPLATE["make_buy"]             = "M"
_TEMPLATE["cost_type"]            = "UNIT"
_TEMPLATE["subcontract_price_eur"] = float("nan")


def _metric_row(df: pd.DataFrame) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Material cost", f"EUR {df['material_cost'].sum():,.2f}")
    c2.metric("Process cost",  f"EUR {df['process_cost'].sum():,.2f}")
    c3.metric("Overhead",      f"EUR {df['overhead'].sum():,.2f}")
    c4.metric("Margin",        f"EUR {df['margin'].sum():,.2f}")
    c5.metric("**TOTAL**",     f"EUR {df['total_cost'].sum():,.2f}")


def _completeness_panel(bom: pd.DataFrame) -> None:
    """Smart completeness widget — shows subsystem coverage and missing items."""
    score = completeness_score(bom)
    present = detect_subsystems(bom)
    missing = common_missing(bom)
    critical_miss = [(p, info) for p, info in missing if info["critical"]]

    pct = int(score * 100)
    label = (
        "✅ Complete waterjet BOM — all subsystems present"
        if pct == 100
        else f"⚠️  BOM completeness: {pct}% — {len(missing)} subsystem(s) missing"
    )

    with st.expander(label, expanded=bool(critical_miss)):
        st.progress(score, text=f"{pct}% of 14 waterjet subsystems detected")

        cols = st.columns(7)
        for i, (prefix, info) in enumerate(WATERJET_SUBSYSTEMS.items()):
            is_present = prefix in present
            count = present.get(prefix, 0)
            status = f"✅ {count} lines" if is_present else ("🔴 **missing**" if info["critical"] else "⬜ not included")
            cols[i % 7].markdown(
                f"{info['icon']} **{info['name']}**  \n{status}  \n"
                f"<small>{info['desc']}</small>",
                unsafe_allow_html=True,
            )

        if critical_miss:
            names = "  •  ".join(f"{info['icon']} **{info['name']}**" for _, info in critical_miss)
            st.error(
                f"**Missing critical subsystems:** {names}  \n"
                "These are essential for a complete waterjet cost estimate. "
                "Download the full template to see reference lines for each subsystem."
            )
        elif missing:
            opt_names = ", ".join(info["name"] for _, info in missing)
            st.info(f"Optional subsystems not included: {opt_names}")
        else:
            st.success("🎉 All 14 waterjet subsystems are present. BOM is complete.")


def _run_calculation(bom: pd.DataFrame, mats: pd.DataFrame, procs: pd.DataFrame,
                     quotes: pd.DataFrame, project_name: str) -> None:
    """Validate, calculate, display results and save. Shared by upload and auto-load."""
    # ── Validate columns ──────────────────────────────────────────────────────
    missing_cols = [c for c in REQUIRED_COLS if c not in bom.columns]
    if missing_cols:
        st.error(f"❌ Missing columns: `{'`, `'.join(missing_cols)}`")
        st.info(f"Required columns: `{'`, `'.join(REQUIRED_COLS)}`")
        return

    for col in ["qty", "mass_kg", "runtime_h"]:
        bom[col] = pd.to_numeric(bom[col], errors="coerce").fillna(0)
    bom["qty"] = bom["qty"].astype("Int64")

    known_mats  = set(mats["material_id"])
    known_procs = set(procs["process_id"])
    unknown_mats  = sorted(set(bom["material_id"].astype(str)) - known_mats)
    unknown_procs = sorted(set(bom["process_route"].astype(str)) - known_procs)

    has_errors = False
    if unknown_mats:
        st.error(
            f"❌ Unknown material_id's: `{'`, `'.join(unknown_mats)}`  \n"
            "Add them to the materials database or adjust the BOM."
        )
        has_errors = True
    if unknown_procs:
        st.error(
            f"❌ Unknown process_route's: `{'`, `'.join(unknown_procs)}`  \n"
            "Add them to the processes database or adjust the BOM."
        )
        has_errors = True
    if has_errors:
        return

    # ── Smart completeness check ──────────────────────────────────────────────
    _completeness_panel(bom)

    score = completeness_score(bom)
    pct   = int(score * 100)
    st.success(
        f"✅ Validation passed — **{len(bom)} lines**, all materials and processes known. "
        f"BOM completeness: **{pct}%**"
    )

    # ── Calculate ─────────────────────────────────────────────────────────────
    mats_q = apply_best_quotes(mats, quotes)
    try:
        with st.status("⚙️ Calculating costs…", expanded=False) as status:
            df = compute_costs(mats_q, procs, bom)
            status.update(label="✅ Calculation complete", state="complete")
    except ValueError as e:
        st.error(f"Calculation failed: {e}")
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.subheader("💶 Cost overview")
    _metric_row(df)

    # ── Cost per subsystem (smart view) ──────────────────────────────────────
    def _subsystem_label(lid: str) -> str:
        upper = str(lid).upper()
        for prefix in sorted(WATERJET_SUBSYSTEMS, key=len, reverse=True):
            if upper.startswith(prefix):
                return f"{WATERJET_SUBSYSTEMS[prefix]['icon']} {WATERJET_SUBSYSTEMS[prefix]['name']}"
        return "Other"

    df["subsystem"] = df["line_id"].apply(_subsystem_label)
    sub_grp = (
        df.groupby("subsystem")[["material_cost", "process_cost", "overhead", "margin", "total_cost"]]
        .sum()
        .sort_values("total_cost", ascending=False)
        .round(2)
    )
    with st.expander("🔩 Costs per waterjet subsystem"):
        st.dataframe(sub_grp, use_container_width=True)

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
    st.dataframe(df[avail_cols].round(4), use_container_width=True, hide_index=True)

    # ── Save + haptic feedback ────────────────────────────────────────────────
    BOM_PATH.write_text(bom.to_csv(index=False), encoding="utf-8")
    st.toast(f"✅ BOM saved — {len(bom)} lines · EUR {df['total_cost'].sum():,.0f} total", icon="💾")

    # Self-learning: record this load
    record_bom_load(bom, project_name)

    if pct == 100:
        st.balloons()

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


def main() -> None:
    home_button()
    st.title("📥 BOM Import & Calculation")
    st.caption(
        "Upload a BOM CSV or recalculate the saved BOM. "
        "Smart completeness checking guides you to a full 14-subsystem waterjet BOM."
    )

    # ── Assembly / project name ───────────────────────────────────────────────
    current_name = load_project_name()
    name_col, _ = st.columns([2, 3])
    new_name = name_col.text_input(
        "🏷️ Assembly / Project name",
        value=current_name,
        placeholder="e.g. Marine Waterjet MWJ-720",
        help="This name appears on all pages and in exported documents.",
    )
    if new_name != current_name:
        save_project_name(new_name)
        st.toast(f"Project name saved: {new_name}", icon="🏷️")

    st.divider()

    # ── Template download ─────────────────────────────────────────────────────
    st.subheader("Step 1 — Download the reference template")
    st.markdown(
        "The template is a **complete 143-line MWJ-720 marine waterjet BOM** covering all 14 subsystems: "
        "Impeller · **Stator Bowl** · Pump Housing · Shaft · **Thrust Block** · Inlet Duct · "
        "Nozzle · Steering · Reverse · Frame · Sealing · Hydraulic · Hardware · QA.  \n"
        "Adjust values for your project and upload below."
    )
    col_dl, col_info = st.columns([1, 3])
    col_dl.download_button(
        label="⬇️  Download BOM template (.csv)",
        data=_TEMPLATE.to_csv(index=False).encode(),
        file_name="bom_template_mwj720_complete.csv",
        mime="text/csv",
        use_container_width=True,
    )
    col_info.markdown(
        "**Required columns:** `line_id` · `material_id` · `qty` · `mass_kg` · `process_route` · `runtime_h`  \n"
        "**Optional columns:** `part_name` · `setup_h` · `yield_factor` · `make_buy` · `cost_type` · `subcontract_price_eur`  \n"
        "_`mass_kg = 0` is valid for process-only rows (NDT, balancing, testing, assembly)._  \n"
        "_`yield_factor` = purchase mass / finished mass (e.g. 0.60 for sand castings, 0.90 for weldments)._  \n"
        "_`setup_h` is amortised across the production run quantity set on Quote Sheet._  \n"
        "**Line ID prefix → subsystem:** "
        "`I` Impeller · `SB` Stator Bowl · `H` Housing · `S` Shaft · `TB` Thrust Block · "
        "`D` Duct · `N` Nozzle · `ST` Steering · `R` Reverse · `F` Frame · "
        "`SE` Sealing · `HY` Hydraulic · `HW` Hardware · `QA` Testing"
    )

    # ── Reference tables ─────────────────────────────────────────────────────
    mats   = load_materials()
    procs  = load_processes()
    quotes = load_quotes()

    c1, c2 = st.columns(2)
    with c1.expander("📋 Available materials"):
        st.dataframe(
            mats[["material_id", "description", "price_eur_per_kg"]],
            use_container_width=True, hide_index=True,
        )
    with c2.expander("⚙️ Available processes"):
        st.dataframe(
            procs[["process_id", "description", "machine_rate_eur_h",
                   "labor_rate_eur_h", "overhead_pct", "margin_pct"]],
            use_container_width=True, hide_index=True,
        )

    # ── Load BOM — upload or auto-load ────────────────────────────────────────
    st.divider()
    st.subheader("Step 2 — Load your BOM")

    tab_upload, tab_saved = st.tabs(["📂 Upload new BOM", "⚡ Recalculate saved BOM"])

    with tab_upload:
        up = st.file_uploader(
            "Drag the file here or click to browse",
            type=["csv"],
            help="Upload a CSV with the 6 required columns shown above.",
        )
        if up:
            try:
                bom = pd.read_csv(up)
            except Exception as e:
                st.error(f"CSV could not be read: {e}")
                return
            st.caption(f"Loaded {len(bom)} lines from **{up.name}**")
            st.dataframe(bom, use_container_width=True, hide_index=True)
            _run_calculation(bom, mats, procs, quotes, new_name or current_name)

    with tab_saved:
        if BOM_PATH.exists():
            try:
                saved_bom = pd.read_csv(BOM_PATH)
                score = completeness_score(saved_bom)
                pct   = int(score * 100)
                st.info(
                    f"**Saved BOM:** `{BOM_PATH}`  \n"
                    f"{len(saved_bom)} lines · completeness {pct}% · "
                    f"last saved automatically on upload"
                )
                if st.button("⚡ Recalculate saved BOM", type="primary",
                             help="Re-run cost calculation on the currently saved BOM."):
                    _run_calculation(saved_bom, mats, procs, quotes, new_name or current_name)
            except Exception as e:
                st.error(f"Could not read saved BOM: {e}")
        else:
            st.info("No saved BOM found yet. Upload a BOM first — it will be saved automatically.")


guard(main)
