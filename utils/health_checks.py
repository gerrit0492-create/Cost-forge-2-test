def missing_columns(df, required):
    return [name for name in required if name not in df.columns]


def duplicate_count(df, column):
    if column not in df.columns:
        return 0
    return int(df[column].duplicated().sum())


def sheet_is_empty(df):
    return len(df) == 0


def status_label(errors, warnings):
    if errors > 0:
        return 'RED'
    if warnings > 0:
        return 'AMBER'
    return 'GREEN'
