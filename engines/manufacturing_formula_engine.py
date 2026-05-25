import math


class ManufacturingFormulaEngine:

    @staticmethod
    def calculate_laser_cut_cost(cut_length_mm, rate_per_meter):

        meters = cut_length_mm / 1000
        total = meters * rate_per_meter

        return {
            'cut_length_mm': cut_length_mm,
            'cut_length_m': meters,
            'rate_per_meter': rate_per_meter,
            'total_cost': total,
        }

    @staticmethod
    def calculate_bending_cost(
        bends,
        cost_per_bend
    ):

        total = bends * cost_per_bend

        return {
            'bends': bends,
            'cost_per_bend': cost_per_bend,
            'total_cost': total,
        }

    @staticmethod
    def calculate_weld_cost(
        weld_length_mm,
        weld_rate_per_meter
    ):

        meters = weld_length_mm / 1000
        total = meters * weld_rate_per_meter

        return {
            'weld_length_mm': weld_length_mm,
            'weld_length_m': meters,
            'weld_rate_per_meter': weld_rate_per_meter,
            'total_cost': total,
        }

    @staticmethod
    def calculate_sheet_weight(
        length_mm,
        width_mm,
        thickness_mm,
        density=7850
    ):

        volume_m3 = (
            (length_mm / 1000) *
            (width_mm / 1000) *
            (thickness_mm / 1000)
        )

        weight = volume_m3 * density

        return {
            'volume_m3': volume_m3,
            'weight_kg': weight,
        }
