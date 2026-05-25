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

st.title('Cost Forge 2.0')
st.caption('Manufacturing Cost Engineering Control Center')

with st.sidebar:
    st.title('Project Controls')

    st.text_input('Active Project', value='DAF Proto Housing Rev-B')

    st.selectbox(
        'Production Plant',
        ['Eindhoven', 'Hamburg', 'Gdansk', 'Prototype Shop']
    )

    st.slider('Target Margin %', 0, 100, 28)
    st.slider('Material Inflation %', -50, 100, 0)
    st.slider('Labor Adjustment %', -50, 100, 0)
    st.slider('Machine Efficiency %', -50, 100, 0)

k1, k2, k3, k4 = st.columns(4)

k1.metric('Projects', '12')
k2.metric('Current Margin', '31.2%')
k3.metric('RFQ Status', 'Pending')
k4.metric('Plant', 'Eindhoven')

st.markdown('## Source Data')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('QMS Prices')
    with st.expander('Open →'):
        render_projects()

with c2:
    st.info('Material Database')
    with st.expander('Open →'):
        render_bom()

with c3:
    st.info('Supplier Database')
    with st.expander('Open →'):
        render_suppliers()

with c4:
    st.info('BOM Import')
    with st.expander('Open →'):
        render_bom()

st.markdown('## Calculate & Size')

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.info('Quick Cost')
    with st.expander('Open →'):
        render_costing()

with c2:
    st.info('Calculation')
    with st.expander('Open →'):
        render_costing()

with c3:
    st.info('Routing Engine')
    with st.expander('Open →'):
        render_routing()

with c4:
    st.info('Scenario Planner')
    with st.expander('Open →'):
        render_scenario_planner()

st.markdown('## Engineering')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('Engineering Analysis')
    with st.expander('Open →'):
        render_engineering_workspace()

with c2:
    st.info('Manufacturing Costing')
    with st.expander('Open →'):
        render_costing()

with c3:
    st.info('Reporting & Analytics')
    with st.expander('Open →'):
        render_reporting()

st.markdown('## Commercial')

c1, c2, c3 = st.columns(3)

with c1:
    st.info('RFQ Workflow')
    with st.expander('Open →'):
        render_rfq()

with c2:
    st.info('Quote Generator')
    with st.expander('Open →'):
        render_quote_generator()

with c3:
    st.info('Dashboard')
    with st.expander('Open →'):
        render_dashboard()
