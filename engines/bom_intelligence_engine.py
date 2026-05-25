def classify_make_buy(category):
    make_categories = [
        'Weldment',
        'Machined',
        'Assembly'
    ]

    if category in make_categories:
        return 'Make'

    return 'Buy'


def detect_duplicate_parts(df, part_column='Part Number'):
    duplicates = df[df.duplicated(part_column, keep=False)]

    return duplicates
