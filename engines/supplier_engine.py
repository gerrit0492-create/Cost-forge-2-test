SUPPLIER_DATA = {
    'Steel Supplier A': 1.25,
    'Steel Supplier B': 1.18,
    'Aluminium Supplier': 2.45,
}


def calculate_supplier_material_cost(material_kg, price_per_kg):
    total = material_kg * price_per_kg

    return {
        'material_kg': material_kg,
        'price_per_kg': price_per_kg,
        'total_material_cost': total,
    }
