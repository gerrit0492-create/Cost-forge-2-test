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
    st.session_state.active_module = 'Home'

if 'scenario_values' not in st.session_state:
    st.session_state.scenario_values = {}

MODULES = {
    'Home': render_home,
    'Projects': render_projects,
    'BOM Import': render_bom,
    'Advanced BOM': render_bom_hierarchy,
    'Engineering Workspace': render_engineering_workspace,
    'Manufacturing Formulas': render_manufacturing_formulas,
    'Routing': render_routing,
    'Costing': render_costing,
    'Scenario Planner': render_scenario_planner,
    'Should Cost Intelligence': render_should_costing,
    'Suppliers': render_suppliers,
    'RFQ Workflow': render_rfq,
    'Quote Generator': render_quote_generator,
    'Forecasting': render_forecasting,
    'Dashboard': render_dashboard,
    'Reporting': render_reporting,
    'Project Save': render_project_save,
}

with st.sidebar:
    st.title('Scenario Controls')

    st.slider(
        'Material Inflation %',
        min_value=-50,
        max_value=100,
        value=int(st.session_state.get('global_material_inflation', 0)),
        key='global_material_inflation'
    )

    st.slider(
        'Labor Rate Adjustment %',
        min_value=-50,
        max_value=100,
        value=int(st.session_state.get('global_labor_adjustment', 0)),
        key='global_labor_adjustment'
    )

    st.slider(
        'Machine Efficiency %',
        min_value=-50,
        max_value=100,
        value=int(st.session_state.get('global_machine_efficiency', 0)),
        key='global_machine_efficiency'
    )

    st.selectbox(
        'Production Plant',
        ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop'],
        key='global_plant'
    )

st.title('Cost Forge 2.0')
st.caption('Manufacturing Cost Engineering Workflow Cockpit')

workflow_rows = [
    ['Projects', 'BOM Import', 'Engineering Workspace', 'Routing'],
    ['Costing', 'Scenario Planner', 'Should Cost Intelligence', 'Dashboard'],
    ['Suppliers', 'RFQ Workflow', 'Quote Generator', 'Reporting'],
]

for row in workflow_rows:
    cols = st.columns(len(row))

    for col, module_name in zip(cols, row):
        with col:
            if st.button(module_name, use_container_width=True):
                st.session_state.active_module = module_name

st.divider()

active_module = st.session_state.active_module

st.subheader(f'Active Module: {active_module}')

MODULES[active_module]()
