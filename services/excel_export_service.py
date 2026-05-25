import pandas as pd


class ExcelExportService:

    @staticmethod
    def export_dataframe(df, path):
        with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)

        return path
