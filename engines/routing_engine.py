import pandas as pd


def calculate_routing_cost(df):
    routing = df.copy()

    routing['Cost'] = (
        routing['Hours'] * routing['Rate']
    )

    total = routing['Cost'].sum()

    return routing, total
