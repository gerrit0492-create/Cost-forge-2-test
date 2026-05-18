from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STR_COLS = ["line_id", "material_id", "qty"]
_NUM_COLS = ["material_cost", "process_cost", "overhead", "total_cost"]


def _prepare_df(df):
    df = df.copy()
    for col in _STR_COLS:
        if col not in df.columns:
            df[col] = ""
    for col in _NUM_COLS:
        if col not in df.columns:
            df[col] = 0.0
    df[_NUM_COLS] = df[_NUM_COLS].fillna(0.0)
    return df


def make_offer_pdf(df, title: str = "Offerte") -> bytes:
    df = _prepare_df(df)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    total = float(df["total_cost"].sum())
    story.append(Paragraph(f"Totaalprijs: <b>EUR {total:,.2f}</b>", styles["Normal"]))

    headers = ["Line", "Material", "Qty", "Mat. cost", "Proc. cost", "Overhead", "Total"]
    rows = [
        [
            str(r["line_id"]),
            str(r["material_id"]),
            str(r["qty"]),
            f"{r['material_cost']:,.2f}",
            f"{r['process_cost']:,.2f}",
            f"{r['overhead']:,.2f}",
            f"{r['total_cost']:,.2f}",
        ]
        for _, r in df.iterrows()
    ]

    t = Table([headers] + rows)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(t)
    doc.build(story)
    return buf.getvalue()
