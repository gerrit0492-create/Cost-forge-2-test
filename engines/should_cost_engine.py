class ShouldCostEngine:

    @staticmethod
    def calculate_should_cost(
        material_cost,
        labor_cost,
        machine_cost,
        overhead_percent,
    ):

        subtotal = (
            material_cost +
            labor_cost +
            machine_cost
        )

        overhead = (
            subtotal *
            (overhead_percent / 100)
        )

        total = subtotal + overhead

        return {
            'material_cost': material_cost,
            'labor_cost': labor_cost,
            'machine_cost': machine_cost,
            'overhead': overhead,
            'should_cost': total,
        }
