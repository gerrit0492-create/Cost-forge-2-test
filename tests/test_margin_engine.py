from engines.margin_engine import calculate_margin


def test_margin():
    result = calculate_margin(2500, 2000)

    assert result['margin_value'] == 500
