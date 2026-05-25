import streamlit as st

from modules.dashboard import render_dashboard
from modules.projects import render_projects
from modules.bom import render_bom
from modules.routing import render_routing
from modules.costing import render_costing
from modules.scenario_planner import render_scenario_planner
from modules.suppliers import render_suppliers
from modules.rfq import render_rfq
from modules.quote_generator import render_quote_generator
from modules.reporting import render_reporting
from modules.engineering_workspace import render_engineering_workspace

st.set_page_config(
    page_title='Cost Forge 2.0',
    layout='wide',
    initial_sidebar_state='expanded'
)

if 'active_module' not in st.session_state:
    st.session_state.active_module = None

MODULES = {
    'projects': render_projects,
    'bom': render_bom,
    'suppliers': render_suppliers,
    'costing': render_costing,
    'routing': render_routing,
    'scenario': render_scenario_planner,
    'engineering': render_engineering_workspace,
    'reporting': render_reporting,
    'rfq': render_rfq,
    'quote': render_quote_generator,
    'dashboard': render_dashboard,
}

with st.sidebar:
    st.title('Project Controls')
    st.text_input('Active Project', value='DAF Proto Housing Rev-B')
    st.selectbox(
        'Production Plant',
        ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop'],
        key='plant_selector'
    )
    st.slider('Target Margin %', 0, 100, 28, key='target_margin')
    st.slider('Material Inflation %', -50, 100, 0, key='material_inflation_global')
    st.slider('Labor Adjustment %', -50, 100, 0, key='labor_adjustment_global')
    st.slider('Machine Efficiency %', -50, 100, 0, key='machine_efficiency_global')

st.title('Cost Forge 2.0')
st.caption('Manufacturing Cost Engineering Control Center')

k1, k2, k3, k4 = st.columns(4)
k1.metric('Projects', '12')
k2.metric('Current Margin', '31.2%')
k3.metric('RFQ Status', 'Pending')
k4.metric('Plant', 'Eindhoven')

st.markdown('## 1. Source Data')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('QMS Prices')
    if st.button('Open →', key='open_projects', use_container_width=True):
        st.session_state.active_module = 'projects'

with c2:
    st.info('Material Database')
    if st.button('Open →', key='open_bom', use_container_width=True):
        st.session_state.active_module = 'bom'

with c3:
    st.info('Supplier Database')
    if st.button('Open →', key='open_suppliers', use_container_width=True):
        st.session_state.active_module = 'suppliers'

with c4:
    st.info('BOM Import')
    if st.button('Open →', key='open_bom_import', use_container_width=True):
        st.session_state.active_module = 'bom'

st.markdown('## 2. Calculate & Size')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('Quick Cost')
    if st.button('Open →', key='open_costing_quick', use_container_width=True):
        st.session_state.active_module = 'costing'

with c2:
    st.info('Calculation')
    if st.button('Open →', key='open_costing_calc', use_container_width=True):
        st.session_state.active_module = 'costing'

with c3:
    st.info('Routing Engine')
    if st.button('Open →', key='open_routing', use_container_width=True):
        st.session_state.active_module = 'routing'

with c4:
    st.info('Scenario Planner')
    if st.button('Open →', key='open_scenario', use_container_width=True):
        st.session_state.active_module = 'scenario'

st.markdown('## 3. Engineering')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('Engineering Analysis')
    if st.button('Open →', key='open_engineering', use_container_width=True):
        st.session_state.active_module = 'engineering'

with c2:
    st.info('Manufacturing Costing')
    if st.button('Open →', key='open_costing_engineering', use_container_width=True):
        st.session_state.active_module = 'costing'

with c3:
    st.info('Reporting & Analytics')
    if st.button('Open →', key='open_reporting', use_container_width=True):
        st.session_state.active_module = 'reporting'

st.markdown('## 4. Commercial')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('RFQ Workflow')
    if st.button('Open →', key='open_rfq', use_container_width=True):
        st.session_state.active_module = 'rfq'

with c2:
    st.info('Quote Generator')
    if st.button('Open →', key='open_quote', use_container_width=True):
        st.session_state.active_module = 'quote'

with c3:
    st.info('Dashboard')
    if st.button('Open →', key='open_dashboard', use_container_width=True):
        st.session_state.active_module = 'dashboard'

st.divider()

if st.session_state.active_module:
    st.success(f"Current Module: {st.session_state.active_module.title()}")

    try:
        MODULES[st.session_state.active_module]()
    except Exception as error:
        st.error(f'Module error: {error}')
