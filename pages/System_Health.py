import streamlit as st
import pandas as pd

from utils.io import load_materials, load_bom, load_processes
from utils.health_checks import (
    missing_columns,
    duplicate_count,
    sheet_is_empty,
    status_label,
)

st.set_page_config(page_title='System Health', layout='wide')

st.title('System Health Center')
st.caption('Stability Release v2')

checks = []
errors = 0
warnings = 0

try:
    materials = load_materials()
    bom = load_bom()
    processes = load_processes()
except Exception as exc:
    st.error(f'Workbook load failed: {exc}')
    st.stop()

materials_missing = missing_columns(materials, ['material_id'])
if materials_missing:
    errors += 1
    checks.append(['Materials schema', 'RED', str(materials_missing)])
else:
    checks.append(['Materials schema', 'GREEN', 'OK'])

bom_missing = missing_columns(bom, ['line_id', 'material_id'])
if bom_missing:
    errors += 1
    checks.append(['BOM schema', 'RED', str(bom_missing)])
else:
    checks.append(['BOM schema', 'GREEN', 'OK'])

process_duplicates = duplicate_count(processes, 'process_id')
if process_duplicates > 0:
    warnings += 1
    checks.append(['Duplicate process IDs', 'AMBER', str(process_duplicates)])
else:
    checks.append(['Duplicate process IDs', 'GREEN', '0'])

if sheet_is_empty(materials):
    errors += 1
    checks.append(['Materials sheet', 'RED', 'Empty'])

if sheet_is_empty(bom):
    errors += 1
    checks.append(['BOM sheet', 'RED', 'Empty'])

if sheet_is_empty(processes):
    errors += 1
    checks.append(['Processes sheet', 'RED', 'Empty'])

status = status_label(errors, warnings)

c1, c2, c3, c4 = st.columns(4)

c1.metric('Overall Status', status)
c2.metric('Errors', errors)
c3.metric('Warnings', warnings)
c4.metric('Materials', len(materials))

st.subheader('Workbook Integrity Checks')

st.dataframe(
    pd.DataFrame(checks, columns=['Check', 'Status', 'Message']),
    use_container_width=True,
    hide_index=True,
)

st.subheader('Dataset Statistics')

stats = pd.DataFrame([
    ['Materials', len(materials), len(materials.columns)],
    ['BOM', len(bom), len(bom.columns)],
    ['Processes', len(processes), len(processes.columns)],
], columns=['Dataset', 'Rows', 'Columns'])

st.dataframe(stats, use_container_width=True, hide_index=True)

st.success('System Health runtime monitoring active')
