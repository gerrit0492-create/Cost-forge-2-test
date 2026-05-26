import streamlit as st
import pandas as pd

st.set_page_config(
    page_title='Cost Forge 2.0',
    layout='wide',
    initial_sidebar_state='collapsed'
)

# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------

if 'active_section' not in st.session_state:
    st.session_state.active_section = 'Source data & databases'

if 'active_tool' not in st.session_state:
    st.session_state.active_tool = 'Cost Update Hub'

# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------

SECTIONS = {
    'Source data & databases': {
        'number': '1',
        'caption': 'All price, material, supplier and market data in one place.',
        'color': '#1683ff',
        'tools': [
            ('💰', 'Cost Update Hub', 'QMS prices, material costs, process rates, supplier quotes and market factors.'),
            ('🏪', 'QMS Prices', 'Component price database — IN01 / NL07, all waterjet sizes.'),
            ('🛒', 'Direct Purchase', 'Supplier prices for all BOM items. Heatmap, RFQ export and coverage risk.'),
            ('🔗', 'CSV Import', 'Import materials and prices from a public Google Sheet or CSV source.'),
            ('🔄', 'Quarterly Update', 'Generate the legacy quarterly price-update workbook and import it back.'),
        ],
    },
    'Calculate & size': {
        'number': '2',
        'caption': 'Run the cost engine and scale to any waterjet bore size.',
        'color': '#5b8def',
        'tools': [
            ('⚡', 'Quick Cost', 'Instant cost summary of the active BOM with best supplier quotes.'),
            ('🧮', 'Calculation', 'Detailed cost calculation per BOM line, subsystem and assembly.'),
            ('📏', 'Size Scaling', 'Scale costs and weight across waterjet bore sizes and variants.'),
            ('🧩', 'Configuration', 'Select cost basis, quote maturity, currency and active plant.'),
        ],
    },
    'BOM engineering': {
        'number': '3',
        'caption': 'BOM import, structure, classification and management.',
        'color': '#2fbf71',
        'tools': [
            ('📥', 'BOM Import', 'Upload, normalize and validate manufacturing BOM files.'),
            ('🌳', 'BOM Hierarchy', 'Build parent-child assembly structures and subsystem grouping.'),
            ('🏷️', 'Part Classification', 'Classify purchased, machined, welded and assembled parts.'),
            ('✅', 'BOM Completeness', 'Check quote coverage, missing prices and invalid BOM lines.'),
        ],
    },
    'Manufacturing engineering': {
        'number': '4',
        'caption': 'Routing, cycle times, operations and process costing.',
        'color': '#8b5cf6',
        'tools': [
            ('🛠️', 'Routing Engine', 'Define operations, setup time, run time and work centers.'),
            ('⚙️', 'CNC Estimation', 'Estimate CNC machining time, labor and machine rate impact.'),
            ('🔥', 'Welding Estimation', 'Estimate welding preparation, weld length, labor and fixtures.'),
            ('🎨', 'Paint & Coating', 'Estimate coating area, paint usage, masking and handling.'),
        ],
    },
    'Cost modeling': {
        'number': '5',
        'caption': 'Material, conversion, overhead, tooling and should-cost models.',
        'color': '#f59e0b',
        'tools': [
            ('💶', 'Material Costing', 'Material weight, price/kg, scrap factor and surcharge calculations.'),
            ('🏭', 'Conversion Cost', 'Labor, machine, energy and overhead conversion cost model.'),
            ('🧰', 'Tooling Cost', 'Tooling, fixtures, prototype and NRE cost recovery.'),
            ('🎯', 'Should Costing', 'Independent should-cost model and gap analysis.'),
        ],
    },
    'Scenario simulation': {
        'number': '6',
        'caption': 'What-if analysis, inflation, margin, currency and supplier impact.',
        'color': '#ef4444',
        'tools': [
            ('📈', 'Inflation Simulation', 'Simulate material, labor and energy inflation impact.'),
            ('📊', 'Margin Simulation', 'Test target margin, sales price and cost reduction scenarios.'),
            ('🌍', 'Plant Comparison', 'Compare Eindhoven, Hamburg, Gdansk and prototype shop rates.'),
            ('🔁', 'Supplier Comparison', 'Compare best quote, preferred supplier and risk-adjusted sourcing.'),
        ],
    },
    'Supplier & procurement': {
        'number': '7',
        'caption': 'RFQ workflow, benchmarking, risk and lead time.',
        'color': '#14b8a6',
        'tools': [
            ('🏷️', 'Supplier Quotes', 'Maintain supplier quote history, validity and quote coverage.'),
            ('📬', 'RFQ Export', 'Create RFQ packages and export supplier request files.'),
            ('⚠️', 'Vendor Risk', 'Track expired quotes, single-source parts and lead time risk.'),
            ('⏱️', 'Lead Time Analysis', 'Analyze supplier lead times and procurement bottlenecks.'),
        ],
    },
    'Commercial & quoting': {
        'number': '8',
        'caption': 'Quote generator, pricing, margin and commercial tools.',
        'color': '#ec4899',
        'tools': [
            ('🧾', 'Quote Generator', 'Generate customer quote breakdowns from validated costing data.'),
            ('💬', 'Sales Support', 'Prepare commercial explanations and cost driver summaries.'),
            ('📑', 'Quote DOCX', 'Generate DOCX quotation documents.'),
            ('📄', 'Quote PDF', 'Generate PDF quotation package.'),
        ],
    },
    'Analytics & reporting': {
        'number': '9',
        'caption': 'KPIs, dashboards, breakdowns and analytics.',
        'color': '#2563eb',
        'tools': [
            ('📊', 'KPI Dashboard', 'Executive cost dashboard with project and quote KPIs.'),
            ('🧱', 'Cost Breakdown', 'Subsystem, commodity and supplier cost breakdown.'),
            ('📉', 'Delta Analysis', 'Compare revisions, quotes and scenario changes.'),
            ('📦', 'Download Center', 'Export Excel, CSV, DOCX and PDF deliverables.'),
        ],
    },
    'AI & optimization': {
        'number': '10',
        'caption': 'AI recommendations, cost reduction and patterns.',
        'color': '#c026d3',
        'tools': [
            ('🤖', 'Cost Reduction AI', 'Generate cost reduction ideas from BOM, routing and supplier data.'),
            ('🔍', 'Pattern Recognition', 'Detect price outliers, repeated issues and quote gaps.'),
            ('♻️', 'Lean Optimization', 'Identify waste, rework risk and process simplification opportunities.'),
            ('🧠', 'Learning Engine', 'Use historical projects to improve future estimates.'),
        ],
    },
    'Project lifecycle': {
        'number': '11',
        'caption': 'Save, version, audit trail, export and reports.',
        'color': '#64748b',
        'tools': [
            ('💾', 'Save Project', 'Save project data, assumptions and selected scenario.'),
            ('🕘', 'Version History', 'Track revisions, estimate maturity and decision history.'),
            ('🧾', 'Audit Trail', 'Document assumptions, source data and approvals.'),
            ('🚀', 'Release Package', 'Prepare final quote and reporting package.'),
        ],
    },
}

subsystems = pd.DataFrame({
    'Subsystem': ['🏠 Pump Housing', '🪣 Stator Bowl', '🌀 Impeller Assembly', '⚙️ Shaft Line', '✅ QA / Testing', '🏗️ Mounting Frame', '🔩 Thrust Block', '🌊 Inlet Duct', '🕹️ Steering System', '🔄 Reverse System'],
    'Cost (€)': [43955, 32512, 31218, 27765, 17544, 17408, 15770, 12301, 9749, 9093],
    'Share': ['18.4%', '13.6%', '13.1%', '11.6%', '7.4%', '7.3%', '6.6%', '5.2%', '4.1%', '3.8%'],
})

# -----------------------------------------------------------------------------
# CSS: dark cockpit + forced light text + hidden default Streamlit nav/sidebar
# -----------------------------------------------------------------------------

st.markdown('''
<style>
:root {
    --cf-bg: #06101d;
    --cf-panel: rgba(10, 25, 46, 0.96);
    --cf-panel-soft: rgba(12, 31, 56, 0.88);
    --cf-border: rgba(96, 165, 250, 0.22);
    --cf-border-strong: rgba(30, 144, 255, 0.70);
    --cf-text: #eef6ff;
    --cf-muted: #9fb5cc;
    --cf-blue: #1683ff;
    --cf-green: #4ade80;
}

section[data-testid="stSidebar"] {display: none !important;}
button[title="View fullscreen"] {display: none !important;}
#MainMenu, footer, header {visibility: hidden;}

.stApp {
    background: radial-gradient(circle at top left, #0c2342 0%, #06101d 38%, #030811 100%) !important;
    color: var(--cf-text) !important;
}

.block-container {
    padding: 1rem 1rem 1.2rem 1rem !important;
    max-width: 100% !important;
}

h1, h2, h3, h4, h5, h6, p, span, label, div, .stMarkdown, .stCaption, .stText {
    color: var(--cf-text) !important;
}

small, .caption, div[data-testid="stCaptionContainer"], div[data-testid="stMarkdownContainer"] p {
    color: var(--cf-muted) !important;
}

.cf-logo {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}
.cf-mark {
    font-weight: 900;
    font-size: 34px;
    line-height: 1;
    color: var(--cf-blue);
    letter-spacing: -2px;
}
.cf-title {font-size: 24px; font-weight: 800; color: var(--cf-text);}
.cf-subtitle {font-size: 13px; color: var(--cf-muted); margin-top: -4px;}

.cf-panel, div[data-testid="stMetric"], div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(180deg, rgba(12,31,56,0.95), rgba(8,20,37,0.95)) !important;
    border: 1px solid var(--cf-border) !important;
    border-radius: 14px !important;
    box-shadow: 0 12px 30px rgba(0,0,0,0.22) !important;
}

div[data-testid="stMetric"] {
    padding: 15px 16px !important;
    min-height: 104px;
}

div[data-testid="stMetricLabel"] p {
    color: #69b7ff !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    letter-spacing: .03em;
}
div[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 24px !important;
    font-weight: 800 !important;
}
div[data-testid="stMetricDelta"] {color: var(--cf-green) !important;}

.stButton > button {
    background: linear-gradient(180deg, rgba(12,31,56,0.88), rgba(7,18,34,0.96)) !important;
    color: #ffffff !important;
    border: 1px solid rgba(130, 180, 255, 0.40) !important;
    border-radius: 10px !important;
    height: 42px !important;
    font-weight: 750 !important;
    transition: all .15s ease-in-out;
}
.stButton > button:hover {
    border-color: var(--cf-blue) !important;
    box-shadow: 0 0 0 2px rgba(22,131,255,0.22) !important;
    transform: translateY(-1px);
}

input, textarea, select, div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
    background-color: rgba(8,20,37,0.95) !important;
    color: #ffffff !important;
    border-color: rgba(130,180,255,0.25) !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--cf-border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

.cf-card-title {
    color: #ffffff !important;
    font-weight: 850;
    font-size: 17px;
    margin-bottom: 9px;
}
.cf-card-text {
    color: #bed0e5 !important;
    font-size: 13px;
    line-height: 1.55;
    min-height: 78px;
}
.cf-section-header {
    display:flex;
    align-items:center;
    gap: 12px;
    margin-bottom: 6px;
}
.cf-badge {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: linear-gradient(135deg, #1683ff, #0046b8);
    color: white;
    font-weight: 900;
}
.cf-section-title {font-size: 23px; font-weight: 850; color: #ffffff;}
.cf-status {color:#4ade80; font-weight:700;}

@media (max-width: 900px) {
    .block-container {padding: .65rem .55rem 1rem .55rem !important;}
    div[data-testid="column"] {width: 100% !important; flex: 1 1 100% !important;}
    div[data-testid="stMetric"] {min-height: 86px; margin-bottom: 8px;}
    .cf-card-text {min-height: auto;}
}
</style>
''', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def open_section(section_name: str) -> None:
    st.session_state.active_section = section_name
    first_tool = SECTIONS[section_name]['tools'][0][1]
    st.session_state.active_tool = first_tool


def open_tool(tool_name: str) -> None:
    st.session_state.active_tool = tool_name


def nav_button(section_name: str) -> None:
    section = SECTIONS[section_name]
    active = st.session_state.active_section == section_name
    label = f"{section['number']}  {section_name}"
    if st.button(label, key=f"nav_{section_name}", use_container_width=True):
        open_section(section_name)
    if active:
        st.caption('● Active section')
    else:
        st.caption(section['caption'])


def tool_card(icon: str, title: str, description: str, idx: int) -> None:
    with st.container(border=True):
        st.markdown(f"<div class='cf-card-title'>{icon} {title}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='cf-card-text'>{description}</div>", unsafe_allow_html=True)
        if st.button('Open →', key=f"open_{st.session_state.active_section}_{title}_{idx}", use_container_width=True):
            open_tool(title)


def render_tool_panel(tool_name: str) -> None:
    st.markdown('---')
    st.subheader(f'{tool_name}')

    if tool_name in ['Cost Update Hub', 'QMS Prices', 'Direct Purchase', 'CSV Import', 'Quarterly Update']:
        left, right = st.columns([1.25, 1])
        with left:
            st.markdown('#### Cost Breakdown by Subsystem')
            chart_data = pd.DataFrame({
                'Subsystem': ['Shaft Line', 'QA / Testing', 'Impeller Assy.', 'Inlet Duct', 'Mounting Frame', 'Pump Housing', 'Jet Nozzle', 'Reverse System', 'Sealing System', 'Fasteners', 'Thrust Block', 'Hydraulic System', 'Stator Bowl'],
                'Cost': [27765, 17544, 31218, 12301, 17408, 43955, 7400, 9093, 6100, 1200, 15770, 5100, 32512],
            }).set_index('Subsystem')
            st.bar_chart(chart_data)
        with right:
            st.markdown('#### Subsystem Cost Overview')
            st.dataframe(subsystems, use_container_width=True, hide_index=True)
        st.success('✅ BOM Completeness — 100% (143 / 143)')

    elif tool_name in ['Quick Cost', 'Calculation', 'Size Scaling', 'Configuration']:
        c1, c2, c3 = st.columns(3)
        c1.metric('Best Quote Cost', '€ 238,570', '+6.2%')
        c2.metric('Estimated Cost / kg', '€ 149', '+4.3%')
        c3.metric('Target Margin', '28%', 'Budget')
        st.info('Calculation engine ready. Use the settings panel to change maturity, target cost and currency.')

    elif tool_name in ['BOM Import', 'BOM Hierarchy', 'Part Classification', 'BOM Completeness']:
        st.info('BOM workflow ready: import → normalize → validate → classify → cost.')
        sample = pd.DataFrame({
            'Part': ['Pump Housing', 'Impeller Assembly', 'Shaft Line', 'QA / Testing'],
            'Qty': [1, 1, 1, 1],
            'Type': ['Machined', 'Assembly', 'Assembly', 'Service'],
            'Status': ['Complete', 'Complete', 'Complete', 'Complete'],
        })
        st.dataframe(sample, use_container_width=True, hide_index=True)

    elif tool_name in ['Routing Engine', 'CNC Estimation', 'Welding Estimation', 'Paint & Coating']:
        c1, c2, c3 = st.columns(3)
        c1.metric('Machine Rate', '€ 85/h')
        c2.metric('Labor Rate', '€ 65/h')
        c3.metric('OEE', '72%')
        st.warning('Routing panel connected to manufacturing engineering workflow.')

    else:
        st.info(f'{tool_name} module selected. This panel is ready for the next functional build step.')

# -----------------------------------------------------------------------------
# Top header
# -----------------------------------------------------------------------------

header_left, header_right = st.columns([7, 3])
with header_left:
    st.markdown("""
    <div class='cf-logo'>
      <div class='cf-mark'>CF</div>
      <div>
        <div class='cf-title'>Cost Forge 2.0</div>
        <div class='cf-subtitle'>Manufacturing Cost Engineering Suite</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with header_right:
    h1, h2 = st.columns(2)
    h1.selectbox('Currency', ['EUR (€)', 'USD ($)'], key='top_currency', label_visibility='collapsed')
    h2.selectbox('Language', ['🇬🇧 EN', '🇳🇱 NL'], key='top_language', label_visibility='collapsed')

# -----------------------------------------------------------------------------
# KPI strip
# -----------------------------------------------------------------------------

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric('TOTAL PROJECT COST', '€ 238,570', '+6.2% vs last revision')
k2.metric('TOTAL WEIGHT', '1,599 kg', '+2.1% vs last revision')
k3.metric('EST. COST / KG', '€ 149', '+4.3% vs last revision')
k4.metric('BOM LINES', '143', '0 vs last revision')
k5.metric('QUOTE COVERAGE', '16 / 16', '100% covered')
k6.metric('EXPIRED QUOTES', '0', 'All up to date')

# -----------------------------------------------------------------------------
# Main cockpit
# -----------------------------------------------------------------------------

nav_col, center_col, settings_col = st.columns([2.6, 5.8, 2.2], gap='medium')

with nav_col:
    for section_name in SECTIONS:
        with st.container(border=True):
            nav_button(section_name)
    st.markdown('---')
    st.caption('Cost Forge 2.0 • v2.0.1')
    st.markdown("<span class='cf-status'>● All systems operational</span>", unsafe_allow_html=True)

with center_col:
    section = SECTIONS[st.session_state.active_section]
    st.markdown(
        f"<div class='cf-section-header'><span class='cf-badge'>{section['number']}</span><span class='cf-section-title'>{st.session_state.active_section}</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(section['caption'])

    tools = section['tools']
    for row_start in range(0, len(tools), 3):
        row_tools = tools[row_start:row_start + 3]
        cols = st.columns(3)
        for i, tool in enumerate(row_tools):
            with cols[i]:
                tool_card(tool[0], tool[1], tool[2], row_start + i)

    render_tool_panel(st.session_state.active_tool)

with settings_col:
    with st.container(border=True):
        st.markdown('### SETTINGS')
        st.selectbox('Currency', ['EUR (€)', 'USD ($)'], key='settings_currency')
        st.radio('Language', ['🇬🇧 EN', '🇳🇱 NL'], key='settings_language')
        st.markdown('---')
        st.markdown('### Estimate settings')
        st.selectbox('Estimate maturity', ['Budget (±15%)', 'Proposal (±8%)', 'Production (±3%)'], key='estimate_maturity')
        st.number_input('Budget / Target Cost (€)', value=0, key='target_cost')
        st.slider('Target margin %', 0, 60, 28, key='settings_margin')
        st.button('Save settings', use_container_width=True)

st.markdown('---')
st.caption('Cost Forge 2.0 — Enterprise Manufacturing Cost Engineering Suite')
