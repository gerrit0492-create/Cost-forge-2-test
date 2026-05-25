import streamlit as st

from engines.manufacturing_formula_engine import (
    ManufacturingFormulaEngine,
)


def render_manufacturing_formulas():

    st.title('Manufacturing Formula Engine')

    tab1, tab2, tab3, tab4 = st.tabs([
        'Laser',
        'Bending',
        'Welding',
        'Sheet Weight'
    ])

    with tab1:

        cut_length = st.number_input(
            'Cut Length (mm)',
            value=5000.0
        )

        cut_rate = st.number_input(
            'Rate per Meter',
            value=2.5
        )

        result = (
            ManufacturingFormulaEngine
            .calculate_laser_cut_cost(
                cut_length,
                cut_rate
            )
        )

        st.metric(
            'Laser Cost',
            f"€ {result['total_cost']:,.2f}"
        )

    with tab2:

        bends = st.number_input(
            'Number of Bends',
            value=6
        )

        bend_rate = st.number_input(
            'Cost per Bend',
            value=0.75
        )

        result = (
            ManufacturingFormulaEngine
            .calculate_bending_cost(
                bends,
                bend_rate
            )
        )

        st.metric(
            'Bending Cost',
            f"€ {result['total_cost']:,.2f}"
        )

    with tab3:

        weld_length = st.number_input(
            'Weld Length (mm)',
            value=2500.0
        )

        weld_rate = st.number_input(
            'Weld Rate per Meter',
            value=8.5
        )

        result = (
            ManufacturingFormulaEngine
            .calculate_weld_cost(
                weld_length,
                weld_rate
            )
        )

        st.metric(
            'Weld Cost',
            f"€ {result['total_cost']:,.2f}"
        )

    with tab4:

        length = st.number_input(
            'Length (mm)',
            value=1000.0
        )

        width = st.number_input(
            'Width (mm)',
            value=500.0
        )

        thickness = st.number_input(
            'Thickness (mm)',
            value=5.0
        )

        result = (
            ManufacturingFormulaEngine
            .calculate_sheet_weight(
                length,
                width,
                thickness
            )
        )

        st.metric(
            'Weight (kg)',
            f"{result['weight_kg']:.2f}"
        )
