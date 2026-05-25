from datetime import datetime


def generate_report_name(prefix='report'):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    return f'{prefix}_{timestamp}.xlsx'
