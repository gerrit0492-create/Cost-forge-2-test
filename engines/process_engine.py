PROCESS_RATES = {
    'Laser Cutting': 85,
    'Bending': 75,
    'Welding': 95,
    'Machining': 120,
    'Assembly': 65,
    'Coating': 55,
}


def calculate_process_cost(process, hours):
    rate = PROCESS_RATES.get(process, 0)
    total = rate * hours

    return {
        'process': process,
        'hours': hours,
        'rate': rate,
        'total_cost': total,
    }
