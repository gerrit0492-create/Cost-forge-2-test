from pathlib import Path

import pandas as pd

from utils.storage_adapters import (
    CsvFolderAdapter,
    ExcelWorkbookAdapter,
    GoogleSheetsAdapterPlaceholder,
)



def test_csv_folder_adapter_roundtrip(tmp_path: Path):
    adapter = CsvFolderAdapter(folder_path=tmp_path)

    df = pd.DataFrame({'a': [1, 2]})
    adapter.write_table('materials', df)

    loaded = adapter.read_table('materials')
    assert len(loaded) == 2



def test_excel_adapter_unknown_table_raises(tmp_path: Path):
    adapter = ExcelWorkbookAdapter(
        workbook_path=tmp_path / 'test.xlsx',
        sheet_map={'materials': 'Materials'},
    )

    try:
        adapter.read_table('unknown')
    except KeyError:
        pass
    else:
        raise AssertionError('Expected KeyError for unknown table')



def test_google_sheets_placeholder_not_enabled():
    adapter = GoogleSheetsAdapterPlaceholder(spreadsheet_id='dummy')

    try:
        adapter.read_table('materials')
    except NotImplementedError:
        pass
    else:
        raise AssertionError('Expected NotImplementedError')
