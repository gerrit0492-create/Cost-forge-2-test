"""
Quote Revision History.
Snapshot and compare quote revisions — full audit trail for disputed contracts.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.currency import fmt
from utils.io import (load_bom, load_materials, load_processes, load_quotes,
                      df_to_excel_bytes)
from utils.nav import home_button
from utils.pricing import compute_costs
from utils.project import load_project_meta, load_project_name
from utils.quotes import apply_best_quotes
from utils.safe import guard
from utils.style import inject_css, page_header

REVISIONS_FILE = Path("data") / "quote_revisions.json"


def _load_revisions() -> list[dict]:
    if REVISIONS_FILE.exists():
        try:
            return json.loads(REVISIONS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_revisions(revisions: list[dict]) -> None:
    REVISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVISIONS_FILE.write_text(json.dumps(revisions, indent=2))


def _snapshot_summary(df: pd.DataFrame, meta: dict, note: str, rev_label: str) -> dict:
    """Build a revision snapshot from current cost data."""
    return {
        "rev":           rev_label,
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "note":          note,
        "maturity":      meta.get("maturity", ""),
        "project":       meta.get("name", ""),
        "target_cost":   meta.get("target_cost", 0),
        "material_cost": round(float(df["material_cost"].sum()), 2),
        "process_cost":  round(float(df["process_cost"].sum()), 2),
        "overhead":      round(float(df["overhead"].sum()), 2),
        "margin":        round(float(df["margin"].sum()), 2),
        "total_cost":    round(float(df["total_cost"].sum()), 2),
        "bom_lines":     int(len(df)),
        "materials":     int(df["material_id"].nunique()),
        "margin_pct":    round(float(df["margin"].sum() / df["base_cost"].sum() * 100)
                               if df["base_cost"].sum() > 0 else 0, 2),
    }


def main() -> None:
    st.set_page_config(page_title="Quote Revisions", layout="wide", page_icon="📜")
    inject_css()
    home_button()
    project = load_project_name()
    page_header(
        title="Quote Revision History",
        icon="📜",
        caption="Snapshot quote revisions for audit trail and change tracking.",
        project=project or "",
    )

    # ── Load current costs ────────────────────────────────────────────────────
    try:
        mats   = load_materials()
        procs  = load_processes()
        bom    = load_bom()
        quotes = load_quotes()
        df     = compute_costs(apply_best_quotes(mats, quotes), procs, bom)
    except Exception as exc:
        st.error(f"Could not load BOM: {exc}")
        st.stop()

    meta      = load_project_meta()
    revisions = _load_revisions()

    tab_snap, tab_history, tab_compare = st.tabs(
        ["📸 Create Snapshot", "📋 Revision History", "🔍 Compare Revisions"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — CREATE SNAPSHOT
    # ══════════════════════════════════════════════════════════════════════════
    with tab_snap:
        st.subheader("Save current quote as revision")
        st.caption(
            "A snapshot captures the current sell price, cost breakdown and key metrics. "
            "Save before any significant change so you have a complete audit trail."
        )

        # Auto-suggest next revision label
        existing_revs = [r.get("rev", "") for r in revisions]
        rev_nums = [int(r[3:]) for r in existing_revs if r.startswith("Rev") and r[3:].isdigit()]
        next_num = (max(rev_nums) + 1) if rev_nums else 1

        col_a, col_b = st.columns(2)
        rev_label = col_a.text_input("Revision label", value=f"Rev{next_num:02d}",
                                      help="e.g. Rev01, Rev-A, Draft-1")
        snap_note = col_b.text_input("Change description",
                                      placeholder="e.g. Updated NAB price +8%, added balance operation")

        # Current state preview
        st.markdown("**Current quote summary (will be saved)**")
        current = _snapshot_summary(df, meta, snap_note, rev_label)
        preview_cols = ["material_cost", "process_cost", "overhead", "margin", "total_cost", "margin_pct"]
        prev_df = pd.DataFrame([{
            "Material €":    fmt(current["material_cost"], 0),
            "Process €":     fmt(current["process_cost"], 0),
            "Overhead €":    fmt(current["overhead"], 0),
            "Margin €":      fmt(current["margin"], 0),
            "Sell price €":  fmt(current["total_cost"], 0),
            "Margin %":      f"{current['margin_pct']:.1f}%",
            "BOM lines":     current["bom_lines"],
            "Maturity":      current["maturity"],
        }])
        st.dataframe(prev_df, use_container_width=True, hide_index=True)

        if rev_label in existing_revs:
            st.warning(f"⚠️ Revision **{rev_label}** already exists — saving will overwrite it.")

        if st.button("📸 Save revision snapshot", type="primary", use_container_width=False):
            if not rev_label:
                st.error("Enter a revision label.")
            else:
                # Remove existing with same label
                revisions = [r for r in revisions if r.get("rev") != rev_label]
                revisions.append(current)
                # Sort by timestamp
                revisions.sort(key=lambda r: r.get("timestamp", ""))
                _save_revisions(revisions)
                st.success(f"✅ Revision **{rev_label}** saved at {current['timestamp'][:19]}.")
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — REVISION HISTORY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_history:
        st.subheader("Revision history")

        if not revisions:
            st.info("No revisions saved yet. Create a snapshot in the 'Create Snapshot' tab.")
        else:
            hist_rows = []
            for r in revisions:
                hist_rows.append({
                    "Rev":          r.get("rev", ""),
                    "Saved":        r.get("timestamp", "")[:19].replace("T", " "),
                    "Description":  r.get("note", ""),
                    "Sell price €": fmt(r.get("total_cost", 0), 0),
                    "Material €":   fmt(r.get("material_cost", 0), 0),
                    "Margin €":     fmt(r.get("margin", 0), 0),
                    "Margin %":     f"{r.get('margin_pct', 0):.1f}%",
                    "Maturity":     r.get("maturity", ""),
                    "Lines":        r.get("bom_lines", ""),
                })
            hist_df = pd.DataFrame(hist_rows)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

            # Show sell price trend
            if len(revisions) > 1:
                st.subheader("Sell price progression")
                trend = pd.DataFrame([{
                    "rev":   r.get("rev", ""),
                    "Sell price €": r.get("total_cost", 0),
                    "Margin %": r.get("margin_pct", 0),
                } for r in revisions]).set_index("rev")
                c1, c2 = st.columns(2)
                with c1:
                    st.line_chart(trend[["Sell price €"]], color="#2196F3")
                with c2:
                    st.line_chart(trend[["Margin %"]], color="#4CAF50")

            # Delete
            st.divider()
            del_rev = st.selectbox("Delete revision", ["—"] + [r.get("rev", "") for r in revisions])
            if del_rev != "—" and st.button(f"🗑️ Delete {del_rev}", type="secondary"):
                revisions = [r for r in revisions if r.get("rev") != del_rev]
                _save_revisions(revisions)
                st.success(f"Deleted {del_rev}.")
                st.rerun()

            # Download all revisions
            def _rev_excel() -> bytes:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    pd.DataFrame(revisions).to_excel(w, sheet_name="Revisions", index=False)
                return buf.getvalue()

            st.download_button(
                "⬇️ Download revision history",
                data=_rev_excel(),
                file_name="quote_revisions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — COMPARE TWO REVISIONS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_compare:
        st.subheader("Compare two revisions")

        if len(revisions) < 2:
            st.info("Need at least 2 saved revisions to compare.")
        else:
            rev_labels = [r.get("rev", "") for r in revisions]
            col_x, col_y = st.columns(2)
            rev_a_lbl = col_x.selectbox("Revision A (baseline)", rev_labels, index=0)
            rev_b_lbl = col_y.selectbox("Revision B (revised)", rev_labels,
                                         index=min(1, len(rev_labels) - 1))

            rev_a = next((r for r in revisions if r.get("rev") == rev_a_lbl), {})
            rev_b = next((r for r in revisions if r.get("rev") == rev_b_lbl), {})

            if rev_a and rev_b:
                fields = [
                    ("Sell price",    "total_cost"),
                    ("Material",      "material_cost"),
                    ("Process",       "process_cost"),
                    ("Overhead",      "overhead"),
                    ("Margin",        "margin"),
                    ("Margin %",      "margin_pct"),
                    ("BOM lines",     "bom_lines"),
                ]
                comp_rows = []
                for label, key in fields:
                    a_val = rev_a.get(key, 0) or 0
                    b_val = rev_b.get(key, 0) or 0
                    delta = b_val - a_val
                    delta_pct = (delta / a_val * 100) if a_val else 0

                    if key == "margin_pct":
                        comp_rows.append({
                            "Element": label,
                            rev_a_lbl: f"{a_val:.1f}%",
                            rev_b_lbl: f"{b_val:.1f}%",
                            "Δ":       f"{delta:+.1f}pp",
                        })
                    elif key == "bom_lines":
                        comp_rows.append({
                            "Element": label,
                            rev_a_lbl: int(a_val),
                            rev_b_lbl: int(b_val),
                            "Δ":       f"{int(delta):+d}",
                        })
                    else:
                        comp_rows.append({
                            "Element": label,
                            rev_a_lbl: fmt(a_val, 0),
                            rev_b_lbl: fmt(b_val, 0),
                            "Δ":       f"{'+' if delta >= 0 else ''}{fmt(delta, 0)} ({delta_pct:+.1f}%)",
                        })

                comp_df = pd.DataFrame(comp_rows)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                sell_delta = (rev_b.get("total_cost", 0) or 0) - (rev_a.get("total_cost", 0) or 0)
                mar_delta  = (rev_b.get("margin_pct", 0) or 0) - (rev_a.get("margin_pct", 0) or 0)

                k1, k2, k3 = st.columns(3)
                k1.metric("Sell price change",
                          fmt(sell_delta, 0),
                          delta=f"{sell_delta/(rev_a.get('total_cost',1) or 1)*100:+.1f}%",
                          delta_color="off")
                k2.metric("Margin change",
                          f"{mar_delta:+.1f}pp",
                          delta="improvement" if mar_delta >= 0 else "erosion",
                          delta_color="normal" if mar_delta >= 0 else "inverse")
                k3.metric("Timestamps",
                          f"{rev_a.get('timestamp','')[:10]} → {rev_b.get('timestamp','')[:10]}")

                # Notes / descriptions
                st.divider()
                col_n1, col_n2 = st.columns(2)
                col_n1.info(f"**{rev_a_lbl}:** {rev_a.get('note', '—') or '—'}")
                col_n2.info(f"**{rev_b_lbl}:** {rev_b.get('note', '—') or '—'}")


guard(main)
