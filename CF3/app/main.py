from __future__ import annotations

import importlib

import streamlit as st

st.set_page_config(
    page_title='Cost Forge 3 Enterprise',
    layout='wide',
    page_icon='🛠️',
)

PAGES = {
    'Dashboard': 'CF3.modules.dashboard',
    'Projects': 'CF3.modules.projects',
    'Command Centre': 'CF3.modules.command_centre',
    'BOM Intelligence': 'CF3.modules.bom_import',
    'Costing': 'CF3.modules.costing',
    'Routing': 'CF3.modules.routing',
    'Suppliers': 'CF3.modules.suppliers',
    'Escalation': 'CF3.modules.escalation',
    'Market Data': 'CF3.modules.market_data',
    'Validation Centre': 'CF3.modules.validation',
    'Management Reporting': 'CF3.modules.reporting',
    'Export Center': 'CF3.modules.export_center',
    'AI Assistant': 'CF3.modules.ai_assistant',
    'Project Close-out': 'CF3.modules.project_closeout',
    'System Health': 'CF3.modules.system_health',
}

st.sidebar.title('Cost Forge 3')
selected_page = st.sidebar.radio('Navigation', list(PAGES.keys()))

st.sidebar.divider()
st.sidebar.caption('CF3 Enterprise Build')
st.sidebar.caption('Modular • Stable • Export-ready')

module_name = PAGES[selected_page]
module = importlib.import_module(module_name)

if hasattr(module, 'render'):
    module.render()
else:
    st.error(f'Module {module_name} has no render() function')
