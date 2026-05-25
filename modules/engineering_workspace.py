import streamlit as st
import pandas as pd


DEFAULT_BOM = pd.DataFrame({
    'Part Number': ['1001', '1002'],
    'Description': ['Bracket', 'Plate'],
    'Qty': [2, 4],
    'Material': ['Steel', 'Aluminium'],
    'Process': ['Laser', 'Bending'],
})


DEFAULT_ROUTING = pd.DataFrame({
    'Operation': ['Laser Cutting', 'Bending'],
    'Hours': [1.5, 0.8],
    'Rate': [85, 75],
})


def render_engineering_workspace():

    st.title('Engineering Workspace')

    tab1, tab2, tab3 = st.tabs([
        'Editable BOM',
        'Routing Editor',
        'Workflow Notes'
    ])

    with tab1:

        st.subheader('Editable BOM Grid')

        edited_bom = st.data_editor(
            DEFAULT_BOM,
            num_rows='dynamic',
            use_container_width=True,
            key='bom_editor'
        )

        st.metric(
            'Total BOM Rows',
            len(edited_bom)
        )

    with tab2:

        st.subheader('Routing Editor')

        edited_routing = st.data_editor(
            DEFAULT_ROUTING,
            num_rows='dynamic',
            use_container_width=True,
            key='routing_editor'
        )

        if (
            'Hours' in edited_routing.columns and
            'Rate' in edited_routing.columns
        ):

            edited_routing['Cost'] = (
                edited_routing['Hours'] *
                edited_routing['Rate']
            )

            st.dataframe(
                edited_routing,
                use_container_width=True
            )

            st.metric(
                'Routing Total',
                f"€ {edited_routing['Cost'].sum():,.2f}"
            )

    with tab3:

        st.subheader('Engineering Workflow Notes')

        st.text_area(
            'Engineering Notes',
            height=250,
            placeholder='Add production notes, tolerances, risks, setup instructions...'
        )

        st.info(
            'Engineering workspace initialized'
        )
