from utils.command_centre_health import calculate_health_score



def test_healthy_project_scores_green():
    result = calculate_health_score(
        data_quality_score=95,
        quote_coverage_pct=98,
        expired_quotes=0,
        open_risks=0,
        margin_pct=0.18,
    )

    assert result.status == 'green'
    assert result.score >= 85



def test_unhealthy_project_scores_red():
    result = calculate_health_score(
        data_quality_score=40,
        quote_coverage_pct=50,
        expired_quotes=5,
        open_risks=6,
        margin_pct=0.03,
    )

    assert result.status == 'red'
    assert result.score < 60
    assert len(result.signals) >= 3
