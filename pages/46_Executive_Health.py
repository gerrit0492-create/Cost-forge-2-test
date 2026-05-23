from __future__ import annotations

import streamlit as st

from utils.command_centre_health import calculate_health_score
from utils.command_centre_ui import render_health_panel
from utils.io import load_materials, load_quotes
from utils.nav import home_button
from utils.quotes import expired_quote_materials
from utils.safe import guard
from utils.style import inject_css, page_header


@st.cache_data(ttl=30)
def _load_health():
    materials = load_materials()
    quotes = load_quotes()

    total_materials = max(1, len(materials))
    quoted_materials = quotes['material_id'].nunique() if not quotes.empty else 0
    quote_coverage_pct = quoted_materials / total_materials * 100

    expired_quotes = len(expired_quote_materials(quotes))

    return calculate_health_score(
        data_quality_score=82,
        quote_coverage_pct=quote_coverage_pct,
        expired_quotes=expired_quotes,
        open_risks=2,
        margin_pct=0.14,
    )


def main() -> None:
    st.set_page_config(page_title='Executive Health', layout='wide', page_icon='🩺')

    inject_css()
    home_button()

    page_header(
        title='Executive Health Monitor',
        icon='🩺',
        caption='Operational project health and executive estimate readiness.',
    )

    health = _load_health()

    render_health_panel(health)

    st.divider()

    col1, col2, col3 = st.columns(3)

    col1.metric('Project Health', f'{health.score}/100')
    col2.metric('Signals', len(health.signals))
    col3.metric('Status', health.status.upper())

    st.caption('Executive Health Monitor for Command Centre V2.')


guard(main)
