import streamlit as st



def render():

    st.title('Operations Centre')
    st.caption('Enterprise operational workflow monitoring')

    c1, c2, c3 = st.columns(3)

    c1.metric('Open RFQs', 12)
    c2.metric('Pending Approvals', 4)
    c3.metric('Active Projects', 9)

    st.success('Operations centre operational')
