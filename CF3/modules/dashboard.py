import streamlit as st


def render():
    st.title('CF3 Dashboard')
    st.caption('Enterprise Manufacturing Cost Platform')

    c1, c2, c3, c4 = st.columns(4)

    c1.metric('Projects', 1)
    c2.metric('BOM Lines', 0)
    c3.metric('Total Cost', '€0')
    c4.metric('System Status', 'OK')

    st.info('CF3 Enterprise Dashboard Active')

    st.subheader('Workflow')
    st.write('BOM Import → Costing → Routing → Supplier Intelligence → Escalation → Export')
