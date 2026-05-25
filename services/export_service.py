import pandas as pd


def export_to_excel(dataframe, path):
    dataframe.to_excel(path, index=False)

    return path
