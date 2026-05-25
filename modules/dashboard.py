import pandas as pd
import streamlit as st


def render_dashboard():
    st.title('Dashboard')

    scenario = st.session_state.get('scenario_values', {})

    total_cost = float(scenario.get('total_cost', 1725.0))
    margin_value = float(scenario.get('margin', 775.0))
    margin_percent = float(scenario.get('margin_percent', 31.0))
    sales_price = float(scenario.get('sales_price', 2500.0))

    c1, c2, c3, c4 = st.columns(4)

    c1.metric('Projects', 12)
    c2.metric('Sales Price', f'EUR {sales_price:,.0f}')
    c3.metric('Total Cost', f'EUR {total_cost:,.0f}')
    c4.metric('Margin %', f'{margin_percent:.1f}%')

    data = pd.DataFrame({
        'Category': ['Sales Price', 'Total Cost', 'Margin'],
        'Value': [sales_price, total_cost, margin_value]
    })

    st.dataframe(data, use_container_width=True, hide_index=True)

    st.bar_chart(data.set_index('Category'))

    trend = pd.DataFrame({
        'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'Revenue': [120000, 145000, 167000, 210000, 225000, 245000],
        'Cost': [82000, 95000, 110000, 135000, 148000, 162000]
    })

    st.line_chart(trend.set_index('Month'))
