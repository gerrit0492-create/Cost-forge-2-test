from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    check: str
    message: str
    count: int = 0


def missing_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> list[str]:
    required = list(required_columns)
    return [column for column in required if column not in df.columns]


def duplicate_values(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame()
    mask = df[column].duplicated(keep=False) & df[column].notna()
    return df.loc[mask].copy()


def negative_numeric_values(df: pd.DataFrame, columns: Iterable[str]) -> dict[str, int]:
    issues: dict[str, int] = {}
    for column in columns:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors='coerce')
        count = int((values < 0).sum())
        if count:
            issues[column] = count
    return issues


def percentage_outliers(df: pd.DataFrame, columns: Iterable[str], max_fraction: float = 1.0) -> dict[str, int]:
    issues: dict[str, int] = {}
    for column in columns:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors='coerce')
        count = int((values > max_fraction).sum())
        if count:
            issues[column] = count
    return issues


def normalize_percentage_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors='coerce')
    return values.where(values <= 1, values / 100)


def validate_dataframe(
    df: pd.DataFrame,
    name: str,
    required_columns: Iterable[str],
    duplicate_key: str | None = None,
    non_negative_columns: Iterable[str] = (),
    percentage_columns: Iterable[str] = (),
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    missing = missing_columns(df, required_columns)
    if missing:
        issues.append(
            ValidationIssue(
                severity='error',
                check='missing_columns',
                message=f'{name} missing columns: {missing}',
                count=len(missing),
            )
        )

    if duplicate_key:
        duplicates = duplicate_values(df, duplicate_key)
        if not duplicates.empty:
            issues.append(
                ValidationIssue(
                    severity='error',
                    check='duplicate_key',
                    message=f'{name} duplicate values in {duplicate_key}',
                    count=len(duplicates),
                )
            )

    negatives = negative_numeric_values(df, non_negative_columns)
    for column, count in negatives.items():
        issues.append(
            ValidationIssue(
                severity='error',
                check='negative_values',
                message=f'{name} has negative values in {column}',
                count=count,
            )
        )

    outliers = percentage_outliers(df, percentage_columns)
    for column, count in outliers.items():
        issues.append(
            ValidationIssue(
                severity='warning',
                check='percentage_outliers',
                message=f'{name} has percentage values above 1.0 in {column}; expected fractions such as 0.12 for 12%',
                count=count,
            )
        )

    return issues
