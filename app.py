import streamlit as st

st.set_page_config(
    page_title='Cost Forge 2.0',
    layout='wide',
    initial_sidebar_state='collapsed'
)

st.markdown('''
<style>
.stApp {
    background: linear-gradient(180deg,#06101d,#081426,#07111d);
    color: white;
}

.block-container {
    padding-top: 1rem;
    max-width: 100%;
}

div[data-testid="stMetric"] {
    background: rgba(9,24,45,0.95);
    padding: 18px;
    border-radius: 16px;
    border: 1px solid rgba(80,140,255,0.15);
}
</style>
''', unsafe_allow_html=True)

# TOP HEADER

left,right = st.columns([8,2])

with left:
    st.title('Cost Forge 2.0')
    st.caption('Manufacturing Cost Engineering Suite')

with right:
    st.selectbox('Currency',['EUR (€)','USD ($)'])

# KPI STRIP

k1,k2,k3,k4,k5,k6 = st.columns(6)

k1.metric('TOTAL PROJECT COST','€ 238,570','+6.2%')
k2.metric('TOTAL WEIGHT','1,599 kg','+2.1%')
k3.metric('EST. COST / KG','€ 149','+4.3%')
k4.metric('BOM LINES','143','0')
k5.metric('QUOTE COVERAGE','16 / 16','100%')
k6.metric('EXPIRED QUOTES','0','All up to date')

# MAIN LAYOUT

nav_col, center_col, settings_col = st.columns([3,5,2])

# LEFT NAVIGATION

with nav_col:

    sections = [
        'Source data & databases',
        'Calculate & size',
        'BOM engineering',
        'Manufacturing engineering',
        'Cost modeling',
        'Scenario simulation',
        'Supplier & procurement',
        'Commercial & quoting',
        'Analytics & reporting',
        'AI & optimization',
        'Project lifecycle'
    ]

    for idx, section in enumerate(sections):
        with st.container(border=True):
            st.markdown(f'### {idx+1}️⃣ {section}')
            st.caption('Enterprise manufacturing workflow section')

# CENTER CONTENT

with center_col:

    st.markdown('## 💰 Cost Update Hub')
    st.caption('All-in-one: QMS prices, material costs, process rates and supplier quotes.')

    cards = st.columns(5)

    card_titles = [
        '💰 Cost Update Hub',
        '🏪 QMS Prices',
        '🛒 Direct Purchase',
        '🔗 CSV Import',
        '🔄 Quarterly Update'
    ]

    for idx,title in enumerate(card_titles):
        with cards[idx]:
            with st.container(border=True):
                st.markdown(f'### {title}')
                st.caption('Enterprise manufacturing tool')
                st.button('Open →', key=f'open_{idx}', use_container_width=True)

    st.markdown('---')

    chart_col, table_col = st.columns([1,1])

    with chart_col:
        st.subheader('Cost Breakdown by Subsystem')
        st.bar_chart({
            'Cost':[43000,32000,28000,17000,12000,9000,7000]
        })

    with table_col:
        st.subheader('Subsystem Overview')
        st.dataframe({
            'Subsystem':['Pump Housing','Impeller','Shaft Line','QA','Frame'],
            '€':[43955,31218,27765,17544,12000],
            'Share':['18.4%','13.1%','11.6%','7.4%','5.2%']
        }, use_container_width=True)

    st.success('✅ BOM Completeness — 100% (143 / 143)')

# RIGHT SETTINGS

with settings_col:

    st.markdown('## SETTINGS')

    st.selectbox('Currency',['EUR (€)','USD ($)'],key='currency_side')

    st.radio('Language',['EN','NL'],key='lang')

    st.markdown('---')

    st.markdown('### Estimate settings')

    st.selectbox(
        'Estimate Maturity',
        ['Budget (±15%)','Proposal','Production']
    )

    st.number_input(
        'Budget / Target Cost (€)',
        value=0
    )

    st.button('Save settings', use_container_width=True)
