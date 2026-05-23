from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandCentreSignal:
    severity: str
    title: str
    message: str


@dataclass(frozen=True)
class CommandCentreHealth:
    score: int
    status: str
    signals: list[CommandCentreSignal]


def classify_status(score: int) -> str:
    if score >= 85:
        return 'green'
    if score >= 60:
        return 'amber'
    return 'red'


def calculate_health_score(
    data_quality_score: int,
    quote_coverage_pct: float,
    expired_quotes: int,
    open_risks: int,
    margin_pct: float,
) -> CommandCentreHealth:
    score = 100
    signals: list[CommandCentreSignal] = []

    if data_quality_score < 80:
        penalty = 20 if data_quality_score < 60 else 10
        score -= penalty
        signals.append(CommandCentreSignal(
            severity='warning',
            title='Data quality below target',
            message=f'Data quality is {data_quality_score}%; review materials, BOM and quote coverage.',
        ))

    if quote_coverage_pct < 80:
        score -= 15
        signals.append(CommandCentreSignal(
            severity='warning',
            title='Quote coverage below target',
            message=f'Quote coverage is {quote_coverage_pct:.0f}%; supplier pricing may be incomplete.',
        ))

    if expired_quotes > 0:
        score -= min(20, expired_quotes * 5)
        signals.append(CommandCentreSignal(
            severity='critical',
            title='Expired quotes detected',
            message=f'{expired_quotes} expired quote(s) should be renewed before firm pricing.',
        ))

    if open_risks > 0:
        score -= min(15, open_risks * 3)
        signals.append(CommandCentreSignal(
            severity='warning',
            title='Open risks require review',
            message=f'{open_risks} open risk(s) remain in the project risk register.',
        ))

    if margin_pct < 0.08:
        score -= 20
        signals.append(CommandCentreSignal(
            severity='critical',
            title='Margin below threshold',
            message=f'Margin is {margin_pct * 100:.1f}%; review cost drivers or sell price.',
        ))

    score = max(0, min(100, score))

    if not signals:
        signals.append(CommandCentreSignal(
            severity='ok',
            title='All core checks nominal',
            message='No critical Command Centre signals detected.',
        ))

    return CommandCentreHealth(
        score=score,
        status=classify_status(score),
        signals=signals,
    )
