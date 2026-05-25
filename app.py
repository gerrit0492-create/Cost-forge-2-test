import streamlit as st

from modules.home import render_home
from modules.dashboard import render_dashboard
from modules.projects import render_projects
from modules.bom import render_bom
from modules.bom_hierarchy import render_bom_hierarchy
from modules.engineering_workspace import render_engineering_workspace
from modules.costing import render_costing
from modules.routing import render_routing
from modules.reporting import render_reporting
from modules.suppliers import render_suppliers
from modules.rfq import render_rfq
from modules.project_save import render_project_save
from modules.forecasting import render_forecasting
from modules.manufacturing_formulas import render_manufacturing_formulas
from modules.quote_generator import render_quote_generator
from modules.should_costing import render_should_costing
from modules.scenario_planner import render_scenario_planner

st.set_page_config(page_title='Cost Forge 2.0', layout='wide')

if 'active_module' not in st.session_state:
    st.session_state.active_module = 'Dashboard'

if 'scenario_values' not in st.session_state:
    st.session_state.scenario_values = {}

MODULES = {
    'Dashboard': render_dashboard,
    'Project Setup': render_projects,
    'BOM Import': render_bom,
    'Engineering Analysis': render_engineering_workspace,
    'Advanced BOM': render_bom_hierarchy,
    'Routing & Operations': render_routing,
    'Manufacturing Formulas': render_manufacturing_formulas,
    'Manufacturing Costing': render_costing,
    'Scenario Simulation': render_scenario_planner,
    'Should Cost Intelligence': render_should_costing,
    'Supplier Management': render_suppliers,
    'RFQ Workflow': render_rfq,
    'Quote Generation': render_quote_generator,
    'Forecasting': render_forecasting,
    'Reporting & Analytics': render_reporting,
    'Project Save': render_project_save,
}

WORKFLOW = [
    ('1', 'Project Setup', 'Project intake and commercial scope'),
    ('2', 'BOM Import', 'Import and structure BOM data'),
    ('3', 'Engineering Analysis', 'DFM and manufacturing review'),
    ('4', 'Routing & Operations', 'Machines, setup and cycle times'),
    ('5', 'Manufacturing Costing', 'Material, labor and overhead'),
    ('6', 'Scenario Simulation', 'Inflation and margin simulation'),
    ('7', 'Supplier Management', 'Supplier sourcing and analysis'),
    ('8', 'RFQ Workflow', 'RFQ preparation and tracking'),
    ('9', 'Quote Generation', 'Commercial quotation workflow'),
    ('10', 'Reporting & Analytics', 'KPI and management reporting'),
]

active_module = st.session_state.active_module

with st.sidebar:
    st.title('Cost Forge Controls')
    st.caption(f'Context: {active_module}')

    if active_module == 'Scenario Simulation':
        st.subheader('Scenario Controls')
        st.slider('Material Inflation %', -50, 100, value=int(st.session_state.get('global_material_inflation', 0)), key='global_material_inflation')
        st.slider('Labor Rate Adjustment %', -50, 100, value=int(st.session_state.get('global_labor_adjustment', 0)), key='global_labor_adjustment')
        st.slider('Machine Efficiency %', -50, 100, value=int(st.session_state.get('global_machine_efficiency', 0)), key='global_machine_efficiency')
        st.selectbox('Production Plant', ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop'], key='global_plant')

    elif active_module == 'BOM Import':
        st.subheader('BOM Controls')
        st.selectbox('Material Class', ['Steel', 'Aluminium', 'Stainless', 'Mixed'])
        st.checkbox('Enable hierarchy view', value=True)
        st.checkbox('Auto detect processes', value=True)

    elif active_module == 'Routing & Operations':
        st.subheader('Routing Controls')
        st.slider('Machine Utilization %', 10, 100, 85)
        st.slider('OEE %', 10, 100, 72)
        st.number_input('Labor Rate EUR/hour', value=65.0)

    elif active_module == 'Manufacturing Costing':
        st.subheader('Costing Controls')
        st.slider('Overhead %', 0, 100, 15)
        st.slider('Target Margin %', 0, 100, 28)
        st.checkbox('Include scrap factor', value=True)

    elif active_module == 'Reporting & Analytics':
        st.subheader('Reporting Controls')
        st.selectbox('Period', ['Monthly', 'Quarterly', 'Yearly'])
        st.checkbox('Compare scenarios', value=True)
        st.checkbox('Show supplier impact', value=True)

    else:
        st.info('Context controls appear per workflow module.')

st.title('Cost Forge 2.0')
st.caption('Manufacturing Cost Engineering Workflow Cockpit')

project_col, kpi1, kpi2, kpi3 = st.columns([2, 1, 1, 1])

with project_col:
    st.success('ACTIVE PROJECT: DAF Proto Housing Rev-B')

with kpi1:
    st.metric('Target Margin', '28%')

with kpi2:
    st.metric('Current Margin', '31.2%')

with kpi3:
    st.metric('RFQ Status', 'Pending')

st.subheader('Workflow Process')

for step, module_name, description in WORKFLOW:
    c1, c2, c3 = st.columns([1, 3, 5])

    with c1:
        st.markdown(f'### {step}')

    with c2:
        if st.button(module_name, use_container_width=True):
            st.session_state.active_module = module_name
            st.rerun()

    with c3:
        st.caption(description)

st.divider()

active_module = st.session_state.active_module

st.subheader(f'Current Module: {active_module}')

MODULES[active_module]()
