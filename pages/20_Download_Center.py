import streamlit as st

from utils.io import workbook_bytes, df_to_excel_bytes, load_bom, load_materials, load_processes, load_quotes
from utils.nav import home_button
from utils.safe import guard


def main():
    home_button()
    st.title("⬇️ Download Center")
    st.caption("Download the full data workbook or individual sheets as Excel files.")

    st.subheader("Full workbook")
    st.download_button(
        "⬇️ Download cost_forge.xlsx (all sheets)",
        data=workbook_bytes(),
        file_name="cost_forge.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Individual sheets")

    sheets = [
        ("BOM",       load_bom,       "bom"),
        ("Materials", load_materials, "materials"),
        ("Processes", load_processes, "processes"),
        ("Quotes",    load_quotes,    "quotes"),
    ]
    cols = st.columns(len(sheets))
    for col, (label, loader, key) in zip(cols, sheets):
        try:
            col.download_button(
                f"⬇️ {label}",
                data=df_to_excel_bytes(loader(), label),
                file_name=f"{key}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            col.error(f"{label}: {e}")


guard(main)
