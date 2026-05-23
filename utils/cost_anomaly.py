from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CostAnomaly:
    severity: str
    category: str
    field: str
    message: str
    count: int = 0


@dataclass(frozen=True)
class CostAnomalyReport:
    score: int
    status: str
    anomalies: list[CostAnomaly]


def _status(score: int) -> str:
    if score >= 85:
        return 'green'
    if score >= 60:
        return 'amber'
    return 'red'


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors='coerce')


def detect_cost_anomalies(cost_df: pd.DataFrame) -> CostAnomalyReport:
    anomalies: list[CostAnomaly] = []
    score = 100

    for column in ['material_cost', 'process_cost', 'overhead', 'margin', 'total_cost']:
        if column not in cost_df.columns:
            score -= 10
            anomalies.append(CostAnomaly(
                severity='critical',
                category='schema',
                field=column,
                message=f'Missing expected costing column: {column}',
                count=1,
            ))

    for column in ['material_cost', 'process_cost', 'overhead', 'total_cost']:
        values = _numeric(cost_df, column)
        if values.empty:
            continue
        negative_count = int((values < 0).sum())
        if negative_count:
            score -= 20
            anomalies.append(CostAnomaly(
                severity='critical',
                category='negative_cost',
                field=column,
                message=f'{negative_count} negative value(s) detected in {column}.',
                count=negative_count,
            ))

    if 'total_cost' in cost_df.columns:
        total_cost = _numeric(cost_df, 'total_cost')
        zero_total = int((total_cost <= 0).sum())
        if zero_total:
            score -= 15
            anomalies.append(CostAnomaly(
                severity='warning',
                category='zero_total',
                field='total_cost',
                message=f'{zero_total} line(s) have zero or negative total cost.',
                count=zero_total,
            ))

        valid = total_cost.dropna()
        if len(valid) >= 4:
            q1 = valid.quantile(0.25)
            q3 = valid.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                upper = q3 + 3 * iqr
                outliers = int((valid > upper).sum())
                if outliers:
                    score -= min(20, outliers * 5)
                    anomalies.append(CostAnomaly(
                        severity='warning',
                        category='cost_outlier',
                        field='total_cost',
                        message=f'{outliers} high total-cost outlier(s) detected using IQR method.',
                        count=outliers,
                    ))

    if {'margin', 'total_cost'}.issubset(cost_df.columns):
        margin = _numeric(cost_df, 'margin')
        total = _numeric(cost_df, 'total_cost')
        margin_pct = margin / total.replace(0, pd.NA)
        negative_margin = int((margin_pct < 0).sum())
        low_margin = int(((margin_pct >= 0) & (margin_pct < 0.05)).sum())

        if negative_margin:
            score -= 20
            anomalies.append(CostAnomaly(
                severity='critical',
                category='margin',
                field='margin',
                message=f'{negative_margin} line(s) have negative margin.',
                count=negative_margin,
            ))

        if low_margin:
            score -= min(15, low_margin * 3)
            anomalies.append(CostAnomaly(
                severity='warning',
                category='margin',
                field='margin',
                message=f'{low_margin} line(s) have margin below 5%.',
                count=low_margin,
            ))

    if {'material_cost', 'process_cost', 'total_cost'}.issubset(cost_df.columns):
        material = _numeric(cost_df, 'material_cost')
        process = _numeric(cost_df, 'process_cost')
        total = _numeric(cost_df, 'total_cost')

        component_sum = material.fillna(0) + process.fillna(0)
        mismatch = abs(component_sum - total.fillna(0)) > total.fillna(0).abs() * 0.75
        mismatch_count = int(mismatch.sum())
        if mismatch_count:
            score -= min(20, mismatch_count * 5)
            anomalies.append(CostAnomaly(
                severity='warning',
                category='cost_structure',
                field='total_cost',
                message=f'{mismatch_count} line(s) have suspicious component-to-total cost relationship.',
                count=mismatch_count,
            ))

    score = max(0, min(100, score))

    if not anomalies:
        anomalies.append(CostAnomaly(
            severity='ok',
            category='system',
            field='all',
            message='No cost anomalies detected.',
            count=0,
        ))

    return CostAnomalyReport(score=score, status=_status(score), anomalies=anomalies)
