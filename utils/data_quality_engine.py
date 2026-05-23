from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DataQualityFinding:
    severity: str
    category: str
    title: str
    message: str
    count: int = 0


@dataclass(frozen=True)
class DataQualityReport:
    score: int
    status: str
    findings: list[DataQualityFinding]


def _status(score: int) -> str:
    if score >= 85:
        return 'green'
    if score >= 60:
        return 'amber'
    return 'red'


def _count_missing(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return len(df)
    values = df[column]
    return int(values.isna().sum() + (values.astype(str).str.strip() == '').sum())


def analyse_data_quality(
    materials: pd.DataFrame,
    bom: pd.DataFrame,
    processes: pd.DataFrame,
    quotes: pd.DataFrame,
) -> DataQualityReport:
    findings: list[DataQualityFinding] = []
    score = 100

    material_ids = set(materials.get('material_id', pd.Series(dtype=str)).dropna().astype(str))
    bom_material_ids = set(bom.get('material_id', pd.Series(dtype=str)).dropna().astype(str))
    process_ids = set(processes.get('process_id', pd.Series(dtype=str)).dropna().astype(str))
    bom_routes = set(bom.get('process_route', pd.Series(dtype=str)).dropna().astype(str))

    missing_material_id = _count_missing(materials, 'material_id')
    if missing_material_id:
        score -= 15
        findings.append(DataQualityFinding('critical', 'materials', 'Missing material IDs', 'Materials table contains empty material_id values.', missing_material_id))

    duplicate_materials = int(materials.get('material_id', pd.Series(dtype=str)).duplicated().sum()) if 'material_id' in materials.columns else 0
    if duplicate_materials:
        score -= 15
        findings.append(DataQualityFinding('critical', 'materials', 'Duplicate material IDs', 'Duplicate material_id values can corrupt pricing joins.', duplicate_materials))

    orphan_material_refs = sorted(bom_material_ids - material_ids)
    if orphan_material_refs:
        score -= min(20, len(orphan_material_refs) * 3)
        findings.append(DataQualityFinding('critical', 'bom', 'BOM references unknown materials', 'BOM contains material_id values not found in materials.', len(orphan_material_refs)))

    orphan_process_refs = sorted(bom_routes - process_ids)
    if orphan_process_refs:
        score -= min(20, len(orphan_process_refs) * 3)
        findings.append(DataQualityFinding('critical', 'routing', 'BOM references unknown process routes', 'BOM process_route values are missing from process master data.', len(orphan_process_refs)))

    if 'price_eur_per_kg' in materials.columns:
        prices = pd.to_numeric(materials['price_eur_per_kg'], errors='coerce')
        no_price = int((prices.isna() | (prices <= 0)).sum())
        if no_price:
            score -= min(15, no_price)
            findings.append(DataQualityFinding('warning', 'pricing', 'Missing or zero material prices', 'One or more materials have no usable price_eur_per_kg.', no_price))
    else:
        score -= 20
        findings.append(DataQualityFinding('critical', 'pricing', 'Missing price column', 'materials table must contain price_eur_per_kg.', 1))

    if not quotes.empty and 'material_id' in quotes.columns and len(material_ids) > 0:
        quoted_ids = set(quotes['material_id'].dropna().astype(str))
        coverage = len(quoted_ids & material_ids) / len(material_ids)
        if coverage < 0.8:
            score -= 10
            findings.append(DataQualityFinding('warning', 'quotes', 'Low supplier quote coverage', f'Quote coverage is {coverage * 100:.0f}%; target is at least 80%.', len(material_ids - quoted_ids)))

    duplicate_bom_lines = int(bom.get('line_id', pd.Series(dtype=str)).duplicated().sum()) if 'line_id' in bom.columns else 0
    if duplicate_bom_lines:
        score -= 10
        findings.append(DataQualityFinding('warning', 'bom', 'Duplicate BOM line IDs', 'Duplicate line_id values make traceability harder.', duplicate_bom_lines))

    for column in ['qty', 'mass_kg', 'runtime_h']:
        if column in bom.columns:
            values = pd.to_numeric(bom[column], errors='coerce')
            negative = int((values < 0).sum())
            if negative:
                score -= 10
                findings.append(DataQualityFinding('critical', 'bom', f'Negative {column}', f'BOM contains negative {column} values.', negative))

    score = max(0, min(100, score))

    if not findings:
        findings.append(DataQualityFinding('ok', 'system', 'Data quality looks healthy', 'No critical data quality findings detected.', 0))

    return DataQualityReport(score=score, status=_status(score), findings=findings)
