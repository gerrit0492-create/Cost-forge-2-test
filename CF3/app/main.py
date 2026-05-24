from __future__ import annotations
import os
import sys

BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import importlib
import streamlit as st

st.set_page_config(
    page_title='Cost Forge 3 Enterprise',
    layout='wide',
    page_icon='🛠️',
)

PAGES = {
    'Home': 'modules.home',
    'Dashboard': 'modules.dashboard',
    'Projects': 'modules.projects',
    'Command Centre': 'modules.command_centre',
    'BOM Intelligence': 'modules.bom_import',
    'Costing': 'modules.costing',
    'Routing': 'modules.routing',
    'Forecasting': 'modules.forecasting',
    'Suppliers': 'modules.suppliers',
    'Escalation': 'modules.escalation',
    'Market Data': 'modules.market_data',
    'Validation Centre': 'modules.validation',
    'Management Reporting': 'modules.reporting',
    'Export Center': 'modules.export_center',
    'AI Assistant': 'modules.ai_assistant',
    'Project Close-out': 'modules.project_closeout',
    'System Health': 'modules.system_health',
}

st.sidebar.title('Cost Forge 3 Enterprise')
selected_page = st.sidebar.radio('Navigation', list(PAGES.keys()))

st.sidebar.divider()
st.sidebar.caption('Unified Manufacturing Cost Platform')
st.sidebar.caption('Enterprise • Modular • Stable')

module_name = PAGES[selected_page]

try:
    module = importlib.import_module(module_name)

    if hasattr(module, 'render'):
        module.render()
    else:
        st.error(f'Module {module_name} has no render() function')

except Exception as e:
    st.error(f'Failed loading module: {module_name}')
    st.exception(e)
