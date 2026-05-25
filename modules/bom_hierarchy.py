import streamlit as st
import pandas as pd

from engines.bom_hierarchy_engine import BOMHierarchyEngine


def render_bom_hierarchy():

    st.title('Advanced BOM Hierarchy')

    uploaded = st.file_uploader(
        'Upload Multi-Level BOM',
        type=['xlsx', 'csv']
    )

    if uploaded:

        if uploaded.name.endswith('.csv'):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)

        st.subheader('BOM Data')

        st.dataframe(
            df,
            use_container_width=True
        )

        try:

            hierarchy = (
                BOMHierarchyEngine
                .build_parent_child_structure(df)
            )

            st.subheader('Parent Child Structure')

            st.json(hierarchy)

            orphans = (
                BOMHierarchyEngine
                .detect_orphans(df)
            )

            st.subheader('Orphan Detection')

            if orphans:
                st.warning(orphans)
            else:
                st.success('No orphan parents detected')

            level_summary = (
                BOMHierarchyEngine
                .summarize_levels(df)
            )

            if not level_summary.empty:

                st.subheader('Level Summary')

                st.dataframe(
                    level_summary,
                    use_container_width=True
                )

        except Exception as e:
            st.error(str(e))
