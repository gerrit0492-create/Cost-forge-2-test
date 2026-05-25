def calculate_subcontract_cost(unit_cost, qty):
    total = unit_cost * qty

    return {
        'unit_cost': unit_cost,
        'qty': qty,
        'subcontract_total': total,
    }
