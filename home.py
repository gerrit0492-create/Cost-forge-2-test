import streamlit as st
import pandas as pd

from cf_core import default_bom, default_assumptions, calculate_costs, subsystem_summary, scenario_matrix, normalize_bom_file, excel_bytes, quote_text

st.set_page_config(page_title='Cost Forge Command Center', page_icon='⚙️', layout='wide')

if 'bom_df' not in st.session_state:
    st.session_state.bom_df = default_bom()
if 'mode' not in st.session_state:
    st.session_state.mode = 'Mission Control'

def euro(v):
    return f'€ {v:,.0f}'

def assumptions():
    d = default_assumptions()
    return {
        'plant': st.session_state.get('plant', d['plant']),
        'estimate_maturity': st.session_state.get('maturity', d['estimate_maturity']),
        'target_margin_pct': float(st.session_state.get('margin', d['target_margin_pct'])),
        'overhead_pct': float(st.session_state.get('overhead', d['overhead_pct'])),
        'scrap_pct': float(st.session_state.get('scrap', d['scrap_pct'])),
        'inflation_pct': float(st.session_state.get('inflation', d['inflation_pct'])),
        'labor_rate_eur_h': float(st.session_state.get('labor', d['labor_rate_eur_h'])),
        'machine_rate_eur_h': float(st.session_state.get('machine', d['machine_rate_eur_h'])),
        'currency': st.session_state.get('currency', d['currency']),
    }

st.title('⚙️ Cost Forge Command Center')
st.caption('New standalone home.py entrypoint — no legacy shell')

ass = assumptions()
costed, s = calculate_costs(st.session_state.bom_df, ass)

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric('Project Cost', euro(s['total_cost']))
k2.metric('Sales Price', euro(s['sales_price']))
k3.metric('Margin Value', euro(s['margin_value']))
k4.metric('Cost / kg', f"€ {s['cost_per_kg']:,.0f}")
k5.metric('Quote Coverage', f"{s['quote_coverage_pct']:.0f}%")
k6.metric('Risk Items', str(s['high_risk_items']))

left, main, right = st.columns([2.4,5.8,2.4], gap='large')

with left:
    st.header('Mission Map')
    for name in ['Mission Control','BOM Lab','Cost Engine','Scenario Lab','Supplier Radar','Quote Room']:
        if st.button(name, key=f'mode_{name}', use_container_width=True):
            st.session_state.mode = name
            st.rerun()

with right:
    st.header('Live Assumptions')
    st.selectbox('Plant', ['Eindhoven','Hamburg','Gdansk','Prototype Shop'], key='plant')
    st.selectbox('Maturity', ['Budget (±15%)','Proposal (±8%)','Production (±3%)'], key='maturity')
    st.slider('Target margin %', 0, 60, int(default_assumptions()['target_margin_pct']), key='margin')
    st.slider('Overhead %', 0, 60, int(default_assumptions()['overhead_pct']), key='overhead')
    st.slider('Scrap %', 0, 25, int(default_assumptions()['scrap_pct']), key='scrap')
    st.slider('Inflation %', -20, 80, int(default_assumptions()['inflation_pct']), key='inflation')
    st.number_input('Labor €/h', min_value=0.0, value=float(default_assumptions()['labor_rate_eur_h']), key='labor')
    st.number_input('Machine €/h', min_value=0.0, value=float(default_assumptions()['machine_rate_eur_h']), key='machine')

with main:
    ass = assumptions()
    costed, s = calculate_costs(st.session_state.bom_df, ass)
    st.header('Always-On Executive Cockpit')
    c1,c2 = st.columns([1.25,1])
    with c1:
        st.bar_chart(costed.groupby('Subsystem')['Total Cost €'].sum().sort_values(ascending=False))
    with c2:
        st.dataframe(subsystem_summary(costed), use_container_width=True, hide_index=True)

    st.divider()
    st.header(st.session_state.mode)

    if st.session_state.mode == 'BOM Lab':
        file = st.file_uploader('Upload BOM CSV or Excel', type=['csv','xlsx'])
        if file is not None:
            st.session_state.bom_df = normalize_bom_file(file)
            st.rerun()
        edited = st.data_editor(st.session_state.bom_df, use_container_width=True, hide_index=True, num_rows='dynamic')
        if st.button('Apply BOM edits', use_container_width=True):
            st.session_state.bom_df = edited
            st.rerun()
    elif st.session_state.mode == 'Cost Engine':
        st.dataframe(costed, use_container_width=True, hide_index=True)
    elif st.session_state.mode == 'Scenario Lab':
        scen = scenario_matrix(st.session_state.bom_df, ass)
        st.dataframe(scen, use_container_width=True, hide_index=True)
        st.line_chart(scen.set_index('Scenario')[['Total Cost €','Sales Price €']])
    elif st.session_state.mode == 'Supplier Radar':
        st.dataframe(costed[['Subsystem','Part','Supplier Quote €','Internal Should Cost €','Quote vs Should Gap €','Risk']], use_container_width=True, hide_index=True)
    elif st.session_state.mode == 'Quote Room':
        txt = quote_text(s, ass)
        st.text_area('Quote summary', txt, height=180)
        st.download_button('Download TXT', txt, 'quote.txt', 'text/plain', use_container_width=True)
        st.download_button('Download CSV', costed.to_csv(index=False), 'costed_bom.csv', 'text/csv', use_container_width=True)
        st.download_button('Download Excel', excel_bytes(costed, s, ass), 'costed_bom.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True)
    else:
        st.success('Mission Control loaded from the new standalone home.py.')
        st.dataframe(subsystem_summary(costed), use_container_width=True, hide_index=True)

st.caption('Cost Forge Command Center — new standalone build')
