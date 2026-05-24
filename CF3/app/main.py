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
    'BOM Intelligence': 'CF3.modules.bom_import',
    'Costing': 'CF3.modules.costing',
    'Routing': 'CF3.modules.routing',
    'Suppliers': 'CF3.modules.suppliers',
    'Escalation': 'CF3.modules.escalation',
    'Export Center': 'CF3.modules.export_center',
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
