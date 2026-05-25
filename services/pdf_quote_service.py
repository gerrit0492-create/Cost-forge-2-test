from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4


class PDFQuoteService:

    @staticmethod
    def generate_quote(
        path,
        customer,
        project,
        total_cost,
        margin_percent,
        sales_price,
    ):

        doc = SimpleDocTemplate(
            path,
            pagesize=A4
        )

        styles = getSampleStyleSheet()

        elements = []

        elements.append(
            Paragraph(
                'Cost Forge 2.0 Quote',
                styles['Title']
            )
        )

        elements.append(Spacer(1, 12))

        lines = [
            f'Customer: {customer}',
            f'Project: {project}',
            f'Total Cost: € {total_cost:,.2f}',
            f'Margin: {margin_percent:.1f}%',
            f'Sales Price: € {sales_price:,.2f}',
        ]

        for line in lines:
            elements.append(
                Paragraph(line, styles['BodyText'])
            )

            elements.append(Spacer(1, 8))

        doc.build(elements)

        return path
