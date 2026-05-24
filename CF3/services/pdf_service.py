from __future__ import annotations

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.tables import Table



def generate_pdf_report(path: str, summary: dict):
    doc = SimpleDocTemplate(path)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph('CF3 Enterprise Report', styles['Heading1']))
    elements.append(Spacer(1, 12))

    table_data = [
        ['Metric', 'Value'],
        ['BOM Lines', str(summary.get('bom_lines', 0))],
        ['Material Cost', str(summary.get('material_cost', 0))],
        ['Routing Cost', str(summary.get('routing_cost', 0))],
        ['Total Cost', str(summary.get('total_cost', 0))],
    ]

    elements.append(Table(table_data))
    doc.build(elements)
