import streamlit as st

st.title('CF3 Dashboard')

c1, c2, c3 = st.columns(3)

c1.metric('Projects', 1)
c2.metric('BOM Lines', 0)
c3.metric('Total Cost', '€0')

st.info('CF3 Enterprise Dashboard Active')
