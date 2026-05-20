import streamlit as st

from utils.io import load_bom, load_materials, load_processes, load_quotes
from utils.pricing import compute_costs
from utils.quotes import apply_best_quotes
from utils.nav import home_button
from utils.safe import guard

_COLS = ["line_id", "material_id", "qty", "material_cost", "process_cost", "overhead", "margin", "total_cost"]


def _to_markdown(df: "pd.DataFrame") -> str:  # noqa: F821
    rows = [df.columns.tolist()] + df.astype(str).values.tolist()
    col_w = [max(len(str(r[i])) for r in rows) for i in range(len(df.columns))]
    def fmt(row):
        return "| " + " | ".join(str(v).ljust(col_w[i]) for i, v in enumerate(row)) + " |"
    sep = "| " + " | ".join("-" * w for w in col_w) + " |"
    return "\n".join([fmt(rows[0]), sep] + [fmt(r) for r in rows[1:]])


def main():
    home_button()
    st.title("📑 Rapport (Markdown)")
    mats   = load_materials()
    procs  = load_processes()
    bom    = load_bom()
    quotes = load_quotes()

    df = compute_costs(apply_best_quotes(mats, quotes), procs, bom)

    md = [
        "# Offerte-rapport",
        f"**Totaal (EUR):** {df['total_cost'].sum():,.2f}",
        "",
        _to_markdown(df[_COLS].round(4)),
    ]
    content = "\n".join(md)
    st.download_button(
        "Download rapport.md", content.encode("utf-8"), "rapport.md", "text/markdown"
    )
    st.code(content, language="markdown")


guard(main)
