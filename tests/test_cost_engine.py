from engines.cost_engine import calculate_total_cost


def test_total_cost():
    result = calculate_total_cost(1000, 500, 10)

    assert result['total_cost'] == 1650
