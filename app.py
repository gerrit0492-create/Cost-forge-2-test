import streamlit as st

from modules.home import render_home
from modules.dashboard import render_dashboard
from modules.projects import render_projects
from modules.bom import render_bom
from modules.costing import render_costing
from modules.routing import render_routing
from modules.reporting import render_reporting

st.set_page_config(page_title='Cost Forge 2.0', layout='wide')

PAGES = {
    'Home': render_home,
    'Dashboard': render_dashboard,
    'Projects': render_projects,
    'BOM Import': render_bom,
    'Costing': render_costing,
    'Routing': render_routing,
    'Reporting': render_reporting,
}

st.sidebar.title('Cost Forge 2.0')
selected_page = st.sidebar.radio('Navigation', list(PAGES.keys()))

PAGES[selected_page]()
