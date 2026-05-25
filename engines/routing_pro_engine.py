def calculate_runtime_cost(runtime_minutes, hourly_rate):
    hours = runtime_minutes / 60
    return hours * hourly_rate


def calculate_setup_runtime_total(
    setup_cost,
    runtime_cost,
    qty
):
    if qty == 0:
        return 0

    return setup_cost + (runtime_cost * qty)
