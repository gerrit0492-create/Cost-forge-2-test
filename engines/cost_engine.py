def calculate_total_cost(material_cost, routing_cost, overhead_percent):
    subtotal = material_cost + routing_cost
    total = subtotal * (1 + overhead_percent / 100)

    return {
        'material_cost': material_cost,
        'routing_cost': routing_cost,
        'overhead_percent': overhead_percent,
        'subtotal': subtotal,
        'total_cost': total,
    }
