import pandas as pd

JET_DATABASE = pd.DataFrame([
    [510,1700,1665,1400,1.00],
    [570,2100,1490,1750,1.10],
    [640,2700,1330,2400,1.24],
    [720,3400,1180,2850,1.42],
    [810,4300,1050,3600,1.65],
    [900,5200,980,4300,1.92],
    [1000,6200,920,5200,2.20],
    [1100,7300,860,6100,2.52],
    [1200,8600,800,7200,2.85],
    [1300,9800,760,8500,3.18],
    [1400,11200,710,9800,3.55],
    [1500,12800,670,11200,3.96],
    [1640,14500,620,12800,4.42],
    [1720,15800,590,14200,4.86],
    [1880,17500,540,16000,5.35],
], columns=['Jet Size','Max Power kW','Max RPM','Mass kg','Scale Factor'])


def get_jet(size:int):
    return JET_DATABASE[JET_DATABASE['Jet Size'] == size].iloc[0]


def scale_cost(base_cost:float, jet_size:int, installed_power:float, shaft_rpm:float, complexity_factor:float=1.2):
    row = get_jet(jet_size)

    power_factor = installed_power / row['Max Power kW']
    rpm_factor = row['Max RPM'] / shaft_rpm

    scaled_cost = (
        base_cost
        * row['Scale Factor']
        * power_factor
        * rpm_factor
        * complexity_factor
    )

    return {
        'jet_size': jet_size,
        'scaled_cost': round(scaled_cost, 2),
        'recommended_sales_price': round(scaled_cost * 1.35, 2),
        'mass_kg': int(row['Mass kg']),
        'power_factor': round(power_factor, 2),
        'rpm_factor': round(rpm_factor, 2),
    }
