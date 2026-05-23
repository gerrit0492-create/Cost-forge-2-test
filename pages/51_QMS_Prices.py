"""QMS Component Price Database
==========================================
Central price database for waterjet QMS components across supply chains
(IN01 = India, NL07 = EU/Netherlands) and all waterjet sizes (MWJ-450 to MWJ-2100).
"""
from __future__ import annotations

import io
import csv
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.nav import home_button
from utils.safe import guard

logger = logging.getLogger(__name__)

REPO_ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR      = REPO_ROOT / "data"
QMS_CSV       = DATA_DIR / "qms_prices.csv"
QMS_LOG       = DATA_DIR / "qms_log.csv"
SUPPLY_CHAINS = ["IN01", "NL07"]
CATEGORIES    = ["Hydraulics", "Sealing", "Structural", "Drive", "Steering", "Electrical", "Other"]
MWJ_SIZES     = [450, 550, 650, 720, 900, 1000, 1200, 1400, 1700, 2100]
BOM_GROUPS    = ["Impeller","Stator Bowl","Housing","Shaft","Thrust Bearing",
                 "Duct","Nozzle","Steering","Reverse","Frame","Seals","Hydraulics","Hardware","QA"]

SC_LABELS = {"IN01": "🇮🇳 IN01 (India)", "NL07": "🇳🇱 NL07 (EU)"}

C_NAVY      = "0D3B66"
C_BLUE      = "1565C0"
C_INPUT_BG  = "FFFDE7"
C_LOCKED_BG = "ECEFF1"
C_WHITE     = "FFFFFF"
C_STRIPE    = "EBF3FF"
C_LIGHT_BG  = "F5F7FA"


# ─── Data I/O ─────────────────────────────────────────────────────────────────

def load_qms() -> pd.DataFrame:
    if not QMS_CSV.exists():
        return pd.DataFrame(columns=[
            "item_id","description","category","supply_chain",
            "size_mm","qty","price_eur","surcharge_pct",
            "supplier","valid_from","notes",
        ])
    df = pd.read_csv(QMS_CSV, dtype=str)
    for col in ("price_eur","surcharge_pct","qty"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["size_mm"] = pd.to_numeric(df["size_mm"], errors="coerce").fillna(0).astype(int)
    df["line_total_eur"] = df["qty"] * df["price_eur"] * (1 + df["surcharge_pct"] / 100)
    return df


def save_qms(df: pd.DataFrame) -> None:
    out = df.drop(columns=["line_total_eur"], errors="ignore")
    out.to_csv(QMS_CSV, index=False)


def _log_update(action: str, detail: str, n_changes: int) -> None:
    entry = {
        "date":      date.today().isoformat(),
        "action":    action,
        "detail":    detail,
        "n_changes": n_changes,
    }
    exists = QMS_LOG.exists()
    with open(QMS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(entry.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(entry)


# ─── Excel helpers ────────────────────────────────────────────────────────────

def _build_qms_excel(df: pd.DataFrame, size: int, sc: str) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    except ImportError:
        st.error("openpyxl is not installed — run: pip install openpyxl")
        st.stop()

    today_str = date.today().strftime("%d %b %Y")
    sc_df = df[(df["supply_chain"] == sc) & (df["size_mm"] == size)].copy()

    def _fill(h): return PatternFill("solid", fgColor=h)
    def _font(bold=False, size=10, color="000000"):
        return Font(bold=bold, size=size, color=color, name="Calibri")
    def _hfont(size=10): return Font(bold=True, size=size, color=C_WHITE, name="Calibri")
    def _center(): return Alignment(horizontal="center", vertical="center", wrap_text=True)
    def _left():   return Alignment(horizontal="left",   vertical="center")
    def _right():  return Alignment(horizontal="right",  vertical="center")
    _thin  = Side(border_style="thin",   color="BDBDBD")
    _thick = Side(border_style="medium", color=C_NAVY)
    def _border(): return Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

    COL_WIDTHS = {"A":3,"B":12,"C":38,"D":14,"E":8,"F":16,"G":16,"H":13,"I":13,"J":16,"K":14}
    HEADERS = [("B","Item ID"),("C","Description"),("D","Group"),("E","Qty"),
               ("F","Current Price (€)"),("G","New Price (€)"),("H","Surcharge %"),
               ("I","Change %"),("J","Line Total (€)"),("K","Supplier")]

    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    ws = wb.create_sheet(f"MWJ-{size} {sc}")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A5"
    for col, w in COL_WIDTHS.items():
        ws.column_dimensions[col].width = w

    ws.row_dimensions[1].height = 6
    ws.merge_cells("B2:K2")
    ws["B2"].value = f"QMS Price Database — MWJ-{size} — {SC_LABELS.get(sc, sc)} — {today_str}"
    ws["B2"].font  = _hfont(size=13); ws["B2"].fill = _fill(C_NAVY); ws["B2"].alignment = _center()
    ws.row_dimensions[2].height = 34

    ws.merge_cells("B3:K3")
    ws["B3"].value = "Fill column G (New Price) and H (Surcharge%). Leave blank to keep current value. Import back via QMS Prices → Import."
    ws["B3"].font  = Font(italic=True, size=10, name="Calibri", color=C_NAVY)
    ws["B3"].fill  = _fill(C_LIGHT_BG); ws["B3"].alignment = _left()
    ws.row_dimensions[3].height = 20

    for col, label in HEADERS:
        iy = col in ("G","H"); ig = col in ("I","J")
        ws[f"{col}4"].value     = label
        ws[f"{col}4"].fill      = _fill(C_INPUT_BG if iy else (C_LOCKED_BG if ig else C_NAVY))
        ws[f"{col}4"].font      = _hfont(9) if not (iy or ig) else Font(bold=True, size=9, color=C_NAVY, name="Calibri")
        ws[f"{col}4"].alignment = _center(); ws[f"{col}4"].border = _border()
    ws.row_dimensions[4].height = 24

    groups = sc_df["notes"].unique()
    current_row = 5
    for grp in BOM_GROUPS:
        grp_df = sc_df[sc_df["notes"] == grp].reset_index(drop=True)
        if grp_df.empty:
            continue
        # Group subheader
        ws.merge_cells(f"B{current_row}:K{current_row}")
        ws[f"B{current_row}"].value     = f"  {grp}"
        ws[f"B{current_row}"].font      = Font(bold=True, size=10, color=C_WHITE, name="Calibri")
        ws[f"B{current_row}"].fill      = _fill(C_BLUE)
        ws[f"B{current_row}"].alignment = _left()
        ws.row_dimensions[current_row].height = 20
        current_row += 1
        grp_first = current_row

        for ridx, row in grp_df.iterrows():
            r = current_row
            stripe = _fill(C_STRIPE) if ridx % 2 == 0 else _fill(C_WHITE)
            for col, val, align in [
                ("B", str(row["item_id"]), _left()),
                ("C", str(row["description"]), _left()),
                ("D", str(row["notes"]), _center()),
                ("E", float(row["qty"]), _right()),
                ("F", float(row["price_eur"]), _right()),
                ("K", str(row.get("supplier","TBD")), _center()),
            ]:
                ws[f"{col}{r}"].value = val; ws[f"{col}{r}"].font = _font(10)
                ws[f"{col}{r}"].fill = stripe; ws[f"{col}{r}"].alignment = align
                ws[f"{col}{r}"].border = _border()
                if col == "F": ws[f"{col}{r}"].number_format = "€#,##0.00"
                if col == "E": ws[f"{col}{r}"].number_format = "0"

            ws[f"G{r}"].fill = _fill(C_INPUT_BG); ws[f"G{r}"].border = _border()
            ws[f"G{r}"].number_format = "€#,##0.00"; ws[f"G{r}"].alignment = _right()

            ws[f"H{r}"].value = float(row["surcharge_pct"])
            ws[f"H{r}"].fill = _fill(C_INPUT_BG); ws[f"H{r}"].border = _border()
            ws[f"H{r}"].number_format = "0.0"; ws[f"H{r}"].alignment = _right()

            ws[f"I{r}"].value = f'=IF(G{r}="","",IF(F{r}=0,"N/A",(G{r}-F{r})/F{r}))'
            ws[f"I{r}"].number_format = "+0.00%;-0.00%"; ws[f"I{r}"].fill = _fill(C_LOCKED_BG)
            ws[f"I{r}"].border = _border(); ws[f"I{r}"].alignment = _right()

            ws[f"J{r}"].value = f'=IF(G{r}="",E{r}*F{r}*(1+H{r}/100),E{r}*G{r}*(1+H{r}/100))'
            ws[f"J{r}"].number_format = "€#,##0.00"; ws[f"J{r}"].fill = _fill(C_LOCKED_BG)
            ws[f"J{r}"].border = _border(); ws[f"J{r}"].alignment = _right()
            ws.row_dimensions[r].height = 18
            current_row += 1

        # Group total
        tr = current_row
        ws.merge_cells(f"B{tr}:I{tr}")
        ws[f"B{tr}"].value = f"{grp} Total"; ws[f"B{tr}"].font = Font(bold=True, size=9, color=C_WHITE, name="Calibri")
        ws[f"B{tr}"].fill = _fill(C_NAVY); ws[f"B{tr}"].alignment = _right(); ws[f"B{tr}"].border = _border()
        for c in "CDEFGHI":
            ws[f"{c}{tr}"].fill = _fill(C_NAVY); ws[f"{c}{tr}"].border = _border()
        ws[f"J{tr}"].value = f"=SUM(J{grp_first}:J{current_row-1})"
        ws[f"J{tr}"].number_format = "€#,##0.00"
        ws[f"J{tr}"].font = Font(bold=True, size=9, color=C_WHITE, name="Calibri")
        ws[f"J{tr}"].fill = _fill(C_NAVY); ws[f"J{tr}"].alignment = _right(); ws[f"J{tr}"].border = _border()
        ws[f"K{tr}"].fill = _fill(C_NAVY); ws[f"K{tr}"].border = _border()
        ws.row_dimensions[tr].height = 18
        current_row += 2

    wb.active = ws
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _read_qms_excel(wb, df: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    new_df = df.copy()
    key_map: dict[tuple, int] = {}
    for idx, row in new_df.iterrows():
        key = (str(row["item_id"]).strip(), str(row["supply_chain"]).strip(), int(row["size_mm"]))
        key_map[key] = idx

    changes: list[dict] = []

    def _sf(val):
        if val is None: return None
        try: return float(str(val).replace(",", "."))
        except: return None

    for ws in wb.worksheets:
        # Parse "MWJ-720 IN01" from sheet name
        parts = ws.title.strip().split()
        if len(parts) < 2: continue
        try:
            size = int(parts[0].replace("MWJ-", ""))
        except ValueError:
            continue
        sc = parts[1] if parts[1] in SUPPLY_CHAINS else None
        if not sc: continue

        for row in ws.iter_rows(min_row=5, values_only=True):
            b_val = row[1] if len(row) > 1 else None
            if not b_val: continue
            b_str = str(b_val).strip()
            if not b_str or "Total" in b_str or b_str.startswith(" "): continue

            item_id = b_str
            key = (item_id, sc, size)
            if key not in key_map: continue
            idx = key_map[key]

            g_val = row[6] if len(row) > 6 else None
            h_val = row[7] if len(row) > 7 else None
            new_price = _sf(g_val)
            new_surch = _sf(h_val)
            cur_price = float(new_df.at[idx, "price_eur"])
            cur_surch  = float(new_df.at[idx, "surcharge_pct"])

            if new_price is not None and abs(new_price - cur_price) > 1e-6:
                changes.append({"key": f"{sc}/{size}/{item_id}", "field": "price_eur",
                                 "old": cur_price, "new": new_price})
                new_df.at[idx, "price_eur"]  = new_price
                new_df.at[idx, "valid_from"] = date.today().isoformat()
            if new_surch is not None and abs(new_surch - cur_surch) > 1e-6:
                changes.append({"key": f"{sc}/{size}/{item_id}", "field": "surcharge_pct",
                                 "old": cur_surch, "new": new_surch})
                new_df.at[idx, "surcharge_pct"] = new_surch
                new_df.at[idx, "valid_from"]    = date.today().isoformat()

    new_df["line_total_eur"] = new_df["qty"] * new_df["price_eur"] * (1 + new_df["surcharge_pct"] / 100)
    return changes, new_df


# ─── Main UI ──────────────────────────────────────────────────────────────────

def main() -> None:
    home_button()
    st.title("🏗️ QMS Component Price Database")
    st.caption("Component purchase prices per BOM line — IN01 (India) and NL07 (EU) — all waterjet sizes.")

    df = load_qms()

    # ── Size + SC selectors ───────────────────────────────────────────────────
    sel_col1, sel_col2, sel_col3 = st.columns([2, 2, 3])
    with sel_col1:
        avail_sizes = sorted(df["size_mm"].unique().tolist()) if not df.empty else MWJ_SIZES
        sel_size = st.selectbox(
            "📐 Waterjet size",
            avail_sizes,
            format_func=lambda s: f"MWJ-{s}",
            key="qms_size",
        )
    with sel_col2:
        sel_sc = st.selectbox(
            "🏭 Supply chain",
            SUPPLY_CHAINS,
            format_func=lambda s: SC_LABELS.get(s, s),
            key="qms_sc",
        )
    with sel_col3:
        grp_opts = ["All"] + BOM_GROUPS
        sel_grp = st.selectbox("📦 BOM group", grp_opts, key="qms_grp")

    # ── Filter ────────────────────────────────────────────────────────────────
    view = df[(df["size_mm"] == sel_size) & (df["supply_chain"] == sel_sc)].copy()
    if sel_grp != "All":
        view = view[view["notes"] == sel_grp]

    # ── KPI strip ─────────────────────────────────────────────────────────────
    priced_n   = int((view["price_eur"] > 0).sum())
    total_n    = len(view)
    bom_total  = view["line_total_eur"].sum()
    unpriced_n = total_n - priced_n

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"MWJ-{sel_size} / {sel_sc} BOM", f"€{bom_total:,.0f}")
    k2.metric("Items in view", total_n)
    k3.metric("✅ Priced", priced_n)
    k4.metric(
        "⚠️ Not priced",
        unpriced_n,
        delta="enter prices below" if unpriced_n else "complete",
        delta_color="inverse" if unpriced_n else "off",
    )

    if unpriced_n:
        st.warning(
            f"**{unpriced_n} item(s) still at €0.00.** "
            "Type the purchase price in the **Price (€)** column below and click **💾 Save**."
        )

    st.divider()

    # ── Direct price editor ───────────────────────────────────────────────────
    st.subheader(f"📋 {sel_grp} — MWJ-{sel_size} / {SC_LABELS.get(sel_sc, sel_sc)}")
    st.caption("Edit any cell in the **Price (€)** or **Surch%** or **Supplier** columns, then click Save.")

    disp = view[["item_id","description","notes","qty",
                 "price_eur","surcharge_pct","line_total_eur","supplier"]].copy()

    edited = st.data_editor(
        disp,
        use_container_width=True,
        hide_index=True,
        column_config={
            "item_id":       st.column_config.TextColumn("Item",        disabled=True, width="small"),
            "description":   st.column_config.TextColumn("Description", disabled=True),
            "notes":         st.column_config.TextColumn("Group",       disabled=True, width="small"),
            "qty":           st.column_config.NumberColumn("Qty",       disabled=True, width="small"),
            "price_eur":     st.column_config.NumberColumn("Price (€)", min_value=0.0, format="€%.2f"),
            "surcharge_pct": st.column_config.NumberColumn("Surch%",    min_value=0.0, format="%.1f%%", width="small"),
            "line_total_eur":st.column_config.NumberColumn("Line Total (€)", disabled=True, format="€%.2f"),
            "supplier":      st.column_config.TextColumn("Supplier",    width="small"),
        },
        key=f"qms_editor_{sel_size}_{sel_sc}_{sel_grp}",
    )

    if st.button("💾 Save", type="primary", key="qms_save"):
        new_df  = df.copy()
        # Match edited rows back by item_id + sc + size
        for _, erow in edited.iterrows():
            mask = (
                (new_df["item_id"]      == erow["item_id"]) &
                (new_df["supply_chain"] == sel_sc) &
                (new_df["size_mm"]      == sel_size)
            )
            if sel_grp != "All":
                mask &= new_df["notes"] == sel_grp
            idxs = new_df[mask].index
            for i in idxs:
                new_df.at[i, "price_eur"]     = erow["price_eur"]
                new_df.at[i, "surcharge_pct"] = erow["surcharge_pct"]
                new_df.at[i, "supplier"]      = erow["supplier"]
                if erow["price_eur"] > 0:
                    new_df.at[i, "valid_from"] = date.today().isoformat()
        new_df["line_total_eur"] = new_df["qty"] * new_df["price_eur"] * (1 + new_df["surcharge_pct"] / 100)
        n_changed = int((edited["price_eur"] > 0).sum())
        save_qms(new_df)
        _log_update("price_edit", f"MWJ-{sel_size} {sel_sc} grp={sel_grp}", n_changed)
        st.success(f"✅ Saved — {n_changed} priced item(s).")
        st.rerun()

    st.divider()

    # ── All-sizes overview ────────────────────────────────────────────────────
    with st.expander("📊 All sizes & supply chains — coverage overview", expanded=False):
        if df.empty:
            st.info("No data.")
        else:
            rows = []
            for sz in sorted(df["size_mm"].unique()):
                for sc in SUPPLY_CHAINS:
                    sub = df[(df["size_mm"] == sz) & (df["supply_chain"] == sc)]
                    if sub.empty: continue
                    p  = int((sub["price_eur"] > 0).sum())
                    t  = len(sub)
                    tot = sub["line_total_eur"].sum()
                    rows.append({
                        "Size":         f"MWJ-{sz}",
                        "SC":           SC_LABELS.get(sc, sc),
                        "Priced":       f"{p}/{t}",
                        "Coverage":     f"{p/t*100:.0f}%",
                        "BOM Total (€)": f"€{tot:,.0f}" if p > 0 else "—",
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    # ── Advanced tabs ─────────────────────────────────────────────────────────
    tab_adj, tab_gen, tab_imp, tab_hist = st.tabs([
        "📈 Apply % Adjustment",
        "📥 Generate Excel",
        "📤 Import Filled Excel",
        "📜 History",
    ])

    # ── TAB: Surcharge ────────────────────────────────────────────────────────
    with tab_adj:
        st.subheader("Apply blanket % price adjustment")
        st.caption("Applies to price_eur for the selected scope. valid_from is updated to today.")

        if df.empty:
            st.info("No data.")
        else:
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                adj_sc  = st.selectbox("Supply chain", ["All"] + SUPPLY_CHAINS, key="adj_sc")
            with ac2:
                adj_sz  = st.selectbox("Size mm", ["All"] + [str(s) for s in sorted(df["size_mm"].unique())], key="adj_sz")
            with ac3:
                adj_grp = st.selectbox("Group", ["All"] + BOM_GROUPS, key="adj_grp")

            pct = st.number_input("% change (e.g. 3.5 = +3.5%, -2 = -2%)", value=0.0, step=0.5, format="%.2f", key="adj_pct")

            mask = pd.Series([True]*len(df), index=df.index)
            if adj_sc  != "All": mask &= df["supply_chain"] == adj_sc
            if adj_sz  != "All": mask &= df["size_mm"]      == int(adj_sz)
            if adj_grp != "All": mask &= df["notes"]         == adj_grp
            n = mask.sum()
            st.info(f"**{n}** item(s) in scope.")

            if st.button("▶️ Apply", type="primary", key="adj_apply", disabled=(n == 0 or pct == 0)):
                new_df = df.copy()
                new_df.loc[mask, "price_eur"] = (new_df.loc[mask, "price_eur"] * (1 + pct/100)).round(2)
                new_df.loc[mask, "valid_from"] = date.today().isoformat()
                new_df["line_total_eur"] = new_df["qty"] * new_df["price_eur"] * (1 + new_df["surcharge_pct"] / 100)
                save_qms(new_df)
                _log_update("price_adjustment", f"sc={adj_sc} sz={adj_sz} grp={adj_grp} pct={pct:+.2f}%", int(n))
                st.success(f"✅ Applied {pct:+.2f}% to {n} item(s).")
                st.rerun()

    # ── TAB: Generate Excel ───────────────────────────────────────────────────
    with tab_gen:
        st.subheader("Generate Excel workbook")
        st.markdown(
            "Generates a workbook for one **Size + Supply chain** combination. "
            "Yellow columns G (New Price) and H (Surcharge%) are editable; grey = formulas. "
            "Import back via **Import Filled Excel**."
        )
        gc1, gc2 = st.columns(2)
        with gc1:
            gen_size = st.selectbox("Size", sorted(df["size_mm"].unique()) if not df.empty else MWJ_SIZES,
                                    format_func=lambda s: f"MWJ-{s}", key="gen_size")
        with gc2:
            gen_sc = st.selectbox("Supply chain", SUPPLY_CHAINS,
                                  format_func=lambda s: SC_LABELS.get(s, s), key="gen_sc")

        if st.button("⚙️ Build workbook", type="primary", key="gen_btn"):
            sub = df[(df["size_mm"] == gen_size) & (df["supply_chain"] == gen_sc)]
            if sub.empty:
                st.warning("No data for this size / supply chain.")
            else:
                with st.spinner("Building …"):
                    try:
                        xb = _build_qms_excel(df, gen_size, gen_sc)
                        st.session_state["qms_xlsx"] = xb
                        st.session_state["qms_xlsx_label"] = f"MWJ-{gen_size}_{gen_sc}"
                        st.success(f"✅ Workbook ready — {len(xb)//1024} KB")
                    except Exception as exc:
                        import traceback
                        st.error(f"Build failed: {exc}")
                        st.code(traceback.format_exc(), language="python")

        if "qms_xlsx" in st.session_state:
            lbl  = st.session_state.get("qms_xlsx_label", "qms")
            fname = f"qms_{lbl}_{date.today().isoformat()}.xlsx"
            st.download_button(
                f"⬇️ Download {fname}",
                data=st.session_state["qms_xlsx"],
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ── TAB: Import ───────────────────────────────────────────────────────────
    with tab_imp:
        st.subheader("Import a filled workbook")
        st.markdown(
            "Upload a workbook generated above. Only non-blank G/H values are applied. "
            "**Dry run** previews changes without writing."
        )
        up   = st.file_uploader("Upload qms_*.xlsx", type=["xlsx"], key="qms_up")
        dry  = st.toggle("🔍 Dry run", value=True, key="qms_dry")
        if dry: st.info("Dry run ON — no files written.")

        if up and st.button("▶️ Import", type="primary", key="qms_imp"):
            try:
                from openpyxl import load_workbook as _lw
                wb = _lw(io.BytesIO(up.read()), data_only=True)
                with st.spinner("Reading …"):
                    changes, new_df = _read_qms_excel(wb, df)

                if not changes:
                    st.warning("No filled-in values found. Make sure you entered prices in column G.")
                else:
                    if dry:
                        st.success(f"**Dry run** — {len(changes)} change(s) found. Disable dry run to apply.")
                    else:
                        save_qms(new_df)
                        _log_update("excel_import", f"file={up.name}", len(changes))
                        st.success(f"✅ {len(changes)} change(s) applied.")
                        st.rerun()

                    st.markdown("**Changes:**")
                    for ch in changes:
                        arrow = "🔺" if ch["new"] > ch["old"] else "🔻"
                        st.markdown(f"- `{ch['key']}` {ch['field']}: **{ch['old']:.2f}** → **{ch['new']:.2f}** {arrow}")
            except Exception as exc:
                st.error(f"Import failed: {exc}")
                logger.exception("_read_qms_excel failed")

    # ── TAB: History ──────────────────────────────────────────────────────────
    with tab_hist:
        st.subheader("Update history")
        if not QMS_LOG.exists():
            st.info("No history yet.")
        else:
            try:
                log = pd.read_csv(QMS_LOG)
                if log.empty:
                    st.info("Log is empty.")
                else:
                    st.dataframe(log.sort_values("date", ascending=False).reset_index(drop=True),
                                 use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Could not read log: {exc}")


guard(main)
