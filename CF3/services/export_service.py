from __future__ import annotations

from io import BytesIO

import pandas as pd



def export_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Costing')

    return output.getvalue()
