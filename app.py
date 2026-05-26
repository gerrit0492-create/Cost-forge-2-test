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

st.set_page_config(page_title='Cost Forge 2.0', layout='wide', initial_sidebar_state='expanded')

if 'active_card' not in st.session_state:
    st.session_state.active_card = None

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
    st.text_input('Active Project', value='DAF Proto Housing Rev-B', key='project_name')
    st.selectbox('Production Plant', ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop'], key='plant_selector')
    st.slider('Target Margin %', 0, 100, 28, key='target_margin')
    st.slider('Material Inflation %', -50, 100, 0, key='material_inflation_global')
    st.slider('Labor Adjustment %', -50, 100, 0, key='labor_adjustment_global')
    st.slider('Machine Efficiency %', -50, 100, 0, key='machine_efficiency_global')

st.title('Cost Forge 2.0')
st.caption('Enterprise Manufacturing Cost Engineering Platform')

k1, k2, k3, k4 = st.columns(4)
k1.metric('Projects', '12')
k2.metric('Current Margin', '31.2%')
k3.metric('RFQ Status', 'Pending')
k4.metric('Plant', 'Eindhoven')

def render_tool_button(title, card_key):
    st.info(title)
    if st.button('Open →', key=f'btn_{card_key}', use_container_width=True):
        if st.session_state.active_card == card_key:
            st.session_state.active_card = None
        else:
            st.session_state.active_card = card_key

def render_active_tool(cards):
    active_card = st.session_state.active_card
    if not active_card:
        return

    for card_title, card_key, module_key in cards:
        if active_card == card_key:
            st.markdown('---')
            st.success(f'{card_title} Active')
            try:
                MODULES[module_key]()
            except Exception as error:
                st.error(f'Module error: {error}')
            return

sections = [
    ('1. Program & Project Setup','Customer RFQ intake and commercial scope.', [('Customer RFQ','rfq_customer','rfq'),('Project Intake','project_intake','projects'),('Revision Control','revision_control','projects'),('Commercial Scope','commercial_scope','projects')]),
    ('2. Source Data & Databases','Centralized manufacturing and supplier databases.', [('QMS Prices','qms_prices','projects'),('Material Database','material_database','bom'),('Supplier Database','supplier_database','suppliers'),('ERP Imports','erp_imports','bom')]),
    ('3. BOM Engineering','Import and structure manufacturing BOMs.', [('BOM Import','bom_import','bom'),('Assembly Structure','assembly_structure','bom'),('Variant Management','variant_management','bom'),('Commodity Grouping','commodity_grouping','bom')]),
    ('4. Manufacturing Engineering','Production engineering and routing analysis.', [('DFM Analysis','dfm_analysis','engineering'),('Routing Engine','routing_engine','routing'),('CNC Estimation','cnc_estimation','engineering'),('Assembly Labor','assembly_labor','engineering')]),
    ('5. Cost Modeling','Manufacturing cost structures and should-cost analysis.', [('Material Costing','material_costing','costing'),('Conversion Cost','conversion_cost','costing'),('Prototype Cost','prototype_cost','costing'),('Should Costing','should_costing','costing')]),
    ('6. Scenario Simulation','Evaluate inflation, margin and supplier impact.', [('Inflation Simulation','inflation_simulation','scenario'),('Margin Simulation','margin_simulation','scenario'),('Plant Comparison','plant_comparison','scenario'),('Supplier Comparison','supplier_comparison','scenario')]),
    ('7. Supplier & Procurement','Supplier sourcing and RFQ benchmarking.', [('Supplier Benchmarking','supplier_benchmarking','suppliers'),('Quote Comparison','quote_comparison','suppliers'),('Vendor Risk','vendor_risk','suppliers'),('Lead Time Analysis','lead_time_analysis','suppliers')]),
    ('8. Commercial & Quoting','Commercial pricing and customer quotations.', [('RFQ Workflow','rfq_workflow','rfq'),('Quote Generator','quote_generator','quote'),('Customer Pricing','customer_pricing','quote'),('Multi-Year Pricing','multi_year_pricing','quote')]),
    ('9. Analytics & Reporting','Executive dashboards and KPI reporting.', [('KPI Dashboard','kpi_dashboard','dashboard'),('Cost Breakdown','cost_breakdown','reporting'),('Risk Analysis','risk_analysis','reporting'),('Executive Dashboard','executive_dashboard','dashboard')]),
    ('10. AI & Optimization','AI-driven manufacturing optimization.', [('Cost Reduction AI','cost_reduction_ai','scenario'),('Pattern Recognition','pattern_recognition','dashboard'),('Lean Optimization','lean_optimization','engineering')])
]

for title, caption, cards in sections:
    st.markdown(f'## {title}')
    st.caption(caption)
    cols = st.columns(4)

    for idx, card in enumerate(cards):
        with cols[idx % 4]:
            render_tool_button(card[0], card[1])

    render_active_tool(cards)
