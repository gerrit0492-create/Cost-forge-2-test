def calculate_margin(sales_price, total_cost):
    margin_value = sales_price - total_cost

    if sales_price == 0:
        margin_percent = 0
    else:
        margin_percent = (
            margin_value / sales_price
        ) * 100

    return {
        'sales_price': sales_price,
        'total_cost': total_cost,
        'margin_value': margin_value,
        'margin_percent': margin_percent,
    }
