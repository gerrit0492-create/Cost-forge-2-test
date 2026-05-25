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

if 'active_tool' not in st.session_state:
    st.session_state.active_tool = 'Dashboard'

if 'scenario_values' not in st.session_state:
    st.session_state.scenario_values = {}

TOOLS = {
    'Dashboard': render_dashboard,
    'Project Setup': render_projects,
    'BOM Import': render_bom,
    'Engineering Analysis': render_engineering_workspace,
    'Routing Engine': render_routing,
    'Manufacturing Costing': render_costing,
    'Scenario Planner': render_scenario_planner,
    'Supplier Management': render_suppliers,
    'RFQ Workflow': render_rfq,
    'Quote Generator': render_quote_generator,
    'Reporting & Analytics': render_reporting,
}

with st.sidebar:
    st.title('Cost Forge Controls')
    st.caption(f'Current Tool: {st.session_state.active_tool}')

    if st.session_state.active_tool == 'Scenario Planner':
        st.subheader('Scenario Controls')

        st.slider('Material Inflation %', -50, 100, value=0, key='material_inflation')
        st.slider('Labor Adjustment %', -50, 100, value=0, key='labor_adjustment')
        st.slider('Machine Efficiency %', -50, 100, value=0, key='machine_efficiency')

        st.selectbox(
            'Production Plant',
            ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop'],
            key='production_plant'
        )

    elif st.session_state.active_tool == 'BOM Import':
        st.subheader('BOM Controls')

        st.file_uploader('Upload BOM', type=['xlsx', 'csv'])

        st.checkbox('Enable Hierarchy Detection', value=True)
        st.checkbox('Auto Detect Processes', value=True)

    elif st.session_state.active_tool == 'Routing Engine':
        st.subheader('Routing Controls')

        st.slider('Machine Utilization %', 10, 100, 85)
        st.slider('OEE %', 10, 100, 72)
        st.number_input('Labor Rate €/hour', value=65.0)

    elif st.session_state.active_tool == 'Manufacturing Costing':
        st.subheader('Cost Controls')

        st.slider('Target Margin %', 0, 100, 28)
        st.slider('Overhead %', 0, 100, 15)

        st.checkbox('Include Scrap Factor', value=True)

    else:
        st.info('Context controls will appear per workflow tool.')

st.title('Cost Forge 2.0')
st.caption('Manufacturing Cost Engineering Control Center')

k1, k2, k3, k4 = st.columns(4)

k1.metric('Projects', '12')
k2.metric('Current Margin', '31.2%')
k3.metric('RFQ Status', 'Pending')
k4.metric('Plant', 'Eindhoven')

st.subheader('Control Center')

st.markdown('## Source Data')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('QMS Prices')
    if st.button('Open →', key='qms_prices', use_container_width=True):
        st.session_state.active_tool = 'Project Setup'

with c2:
    st.info('Material Database')
    if st.button('Open →', key='material_db', use_container_width=True):
        st.session_state.active_tool = 'BOM Import'

with c3:
    st.info('Supplier Database')
    if st.button('Open →', key='supplier_db', use_container_width=True):
        st.session_state.active_tool = 'Supplier Management'

with c4:
    st.info('BOM Import')
    if st.button('Open →', key='bom_import', use_container_width=True):
        st.session_state.active_tool = 'BOM Import'

st.markdown('## Calculate & Size')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('Quick Cost')
    if st.button('Open →', key='quick_cost', use_container_width=True):
        st.session_state.active_tool = 'Manufacturing Costing'

with c2:
    st.info('Calculation')
    if st.button('Open →', key='calculation', use_container_width=True):
        st.session_state.active_tool = 'Manufacturing Costing'

with c3:
    st.info('Routing Engine')
    if st.button('Open →', key='routing_engine', use_container_width=True):
        st.session_state.active_tool = 'Routing Engine'

with c4:
    st.info('Scenario Planner')
    if st.button('Open →', key='scenario_planner', use_container_width=True):
        st.session_state.active_tool = 'Scenario Planner'

st.markdown('## Engineering')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('Engineering Analysis')
    if st.button('Open →', key='engineering_analysis', use_container_width=True):
        st.session_state.active_tool = 'Engineering Analysis'

with c2:
    st.info('Manufacturing Costing')
    if st.button('Open →', key='manufacturing_costing', use_container_width=True):
        st.session_state.active_tool = 'Manufacturing Costing'

with c3:
    st.info('Reporting & Analytics')
    if st.button('Open →', key='reporting', use_container_width=True):
        st.session_state.active_tool = 'Reporting & Analytics'

st.markdown('## Commercial')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('RFQ Workflow')
    if st.button('Open →', key='rfq', use_container_width=True):
        st.session_state.active_tool = 'RFQ Workflow'

with c2:
    st.info('Quote Generator')
    if st.button('Open →', key='quote_generator', use_container_width=True):
        st.session_state.active_tool = 'Quote Generator'

with c3:
    st.info('Dashboard')
    if st.button('Open →', key='dashboard', use_container_width=True):
        st.session_state.active_tool = 'Dashboard'

st.divider()

st.success(f'Active Tool: {st.session_state.active_tool}')

try:
    TOOLS[st.session_state.active_tool]()
except Exception as error:
    st.error(f'Tool loading error: {st.session_state.active_tool}')
    st.exception(error)
