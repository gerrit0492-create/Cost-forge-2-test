import streamlit as st

from modules.home import render_home
from modules.dashboard import render_dashboard
from modules.projects import render_projects
from modules.bom import render_bom
from modules.bom_hierarchy import render_bom_hierarchy
from modules.costing import render_costing
from modules.routing import render_routing
from modules.reporting import render_reporting
from modules.suppliers import render_suppliers
from modules.rfq import render_rfq
from modules.project_save import render_project_save
from modules.forecasting import render_forecasting

st.set_page_config(
    page_title='Cost Forge 2.0',
    layout='wide'
)

PAGES = {
    'Home': render_home,
    'Dashboard': render_dashboard,
    'Projects': render_projects,
    'BOM Import': render_bom,
    'Advanced BOM Hierarchy': render_bom_hierarchy,
    'Costing': render_costing,
    'Routing': render_routing,
    'Suppliers': render_suppliers,
    'RFQ Workflow': render_rfq,
    'Project Save': render_project_save,
    'Forecasting': render_forecasting,
    'Reporting': render_reporting,
}

st.sidebar.title('Cost Forge 2.0')

selected_page = st.sidebar.radio(
    'Navigation',
    list(PAGES.keys())
)

PAGES[selected_page]()
