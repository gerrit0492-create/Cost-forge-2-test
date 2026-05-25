def calculate_setup_cost(setup_hours, hourly_rate):
    total = setup_hours * hourly_rate

    return {
        'setup_hours': setup_hours,
        'hourly_rate': hourly_rate,
        'setup_cost': total,
    }
