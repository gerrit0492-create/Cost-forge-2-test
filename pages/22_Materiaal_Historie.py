# pages/22_Materiaal_Historie.py
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Optional

import pandas as pd
import streamlit as st

from utils.history import (
    build_history_df,
    diff_vs_latest,
    find_anomalies,
    get_price_series,
    load_materials,
    save_snapshot_current,
)
from utils.nav import home_button
from utils.safe import guard


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    if df is None or df.empty:
        return b""
    return df.to_csv(index=False).encode("utf-8")


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content or b"")
    return buf.getvalue()


def _date_bounds(df: pd.DataFrame) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    if df.empty or "date" not in df.columns:
        return None, None
    return df["date"].min(), df["date"].max()


def main():
    home_button()
    st.title("📈 Materiaal-historie & snapshots")

    mats = load_materials()
    if mats.empty:
        st.error("materials_db.csv is leeg.")
        return

    # ======= Sidebar filters =======
    st.sidebar.header("Filters")
    all_ids = list(mats["material_id"].astype(str).unique())
    pick_mode = st.sidebar.radio("Keuze", ["Eén materiaal", "Meerdere materialen"], horizontal=True)

    if pick_mode == "Eén materiaal":
        mid = st.sidebar.selectbox("Materiaal", all_ids, index=0)
        sel_ids = [mid]
    else:
        sel_ids = st.sidebar.multiselect(
            "Materialen", all_ids, default=all_ids[: min(5, len(all_ids))]
        )

    # Volledige historie voor selectie
    hist = build_history_df(sel_ids).copy()
    if "date" in hist.columns and not pd.api.types.is_datetime64_any_dtype(hist["date"]):
        hist["date"] = pd.to_datetime(hist["date"], errors="coerce")

    dmin, dmax = _date_bounds(hist)
    if dmin is not None:
        d_from, d_to = st.sidebar.date_input(
            "Periode",
            value=(dmin.date(), dmax.date()),
            min_value=dmin.date(),
            max_value=dmax.date(),
        )
        # Filter op periode
        if isinstance(d_from, datetime):
            d_from = d_from.date()
        if isinstance(d_to, datetime):
            d_to = d_to.date()
        if "date" in hist.columns:
            hist = hist[
                (hist["date"] >= pd.Timestamp(d_from)) & (hist["date"] <= pd.Timestamp(d_to))
            ]

    # ======= Acties (snapshots & diffs) =======
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📸 Snapshot van huidige materials opslaan"):
            p = save_snapshot_current()
            st.success(f"Snapshot opgeslagen: **{p.name}**")

    with c2:
        dif = diff_vs_latest()
        if dif.empty:
            st.info("Nog geen diff t.o.v. laatste snapshot.")
        else:
            anomalies = find_anomalies(dif)
            st.metric("Afwijkingen > 25%", len(anomalies))
            with st.expander("⚠️ Afwijkingen (vs. laatste snapshot)"):
                st.dataframe(
                    anomalies[["material_id", "old_price", "new_price", "pct_change"]],
                    use_container_width=True,
                )
            st.download_button(
                "Download diff.csv",
                data=_to_csv_bytes(dif),
                file_name="diff_vs_latest.csv",
                mime="text/csv",
            )

    with c3:
        # Verzamel huidige exports in één ZIP
        files_to_zip: dict[str, bytes] = {}
        if not hist.empty:
            files_to_zip["history.csv"] = _to_csv_bytes(hist)
        if "dif" in locals() and not dif.empty:
            files_to_zip["diff_vs_latest.csv"] = _to_csv_bytes(dif)
        if "anomalies" in locals() and not anomalies.empty:
            files_to_zip["anomalies.csv"] = _to_csv_bytes(anomalies)
        st.download_button(
            "⬇️ Download alles (ZIP)",
            data=_zip_bytes(files_to_zip or {"README.txt": b"Geen data"}),
            file_name="material_history_export.zip",
            mime="application/zip",
        )

    # ======= Visualisatie =======
    st.subheader("Historie — grafiek")
    if hist.empty:
        st.info("Geen historie gevonden binnen de huidige filters.")
    else:
        # Eén materiaal: simpele lijn; meerdere: pivot naar wide
        if pick_mode == "Eén materiaal":
            series = get_price_series(sel_ids[0])
            if not series.empty:
                chart = series.rename(columns={"price_eur_per_kg": "EUR/kg"}).set_index("date")
                st.line_chart(chart)
            st.dataframe(series, use_container_width=True)
        else:
            wide = hist.pivot_table(
                index="date", columns="material_id", values="price_eur_per_kg", aggfunc="last"
            ).sort_index()
            st.line_chart(wide)
            with st.expander("Toon tabel (gepivot)"):
                st.dataframe(wide.reset_index(), use_container_width=True)

    # ======= Totaaltabel voor export =======
    st.subheader("Historie — tabel (lang formaat)")
    st.dataframe(hist, use_container_width=True)
    st.download_button(
        "Download history.csv",
        data=_to_csv_bytes(hist),
        file_name="history.csv",
        mime="text/csv",
    )


guard(main)
