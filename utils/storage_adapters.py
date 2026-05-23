from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd


class TableReader(Protocol):
    def read_table(self, name: str) -> pd.DataFrame:
        ...


class TableWriter(Protocol):
    def write_table(self, name: str, df: pd.DataFrame) -> None:
        ...


@dataclass(frozen=True)
class ExcelWorkbookAdapter:
    workbook_path: Path
    sheet_map: dict[str, str]

    def read_table(self, name: str) -> pd.DataFrame:
        if name not in self.sheet_map:
            raise KeyError(f'Unknown table: {name}')
        if not self.workbook_path.exists():
            raise FileNotFoundError(f'Workbook not found: {self.workbook_path}')
        return pd.read_excel(self.workbook_path, sheet_name=self.sheet_map[name])

    def write_table(self, name: str, df: pd.DataFrame) -> None:
        if name not in self.sheet_map:
            raise KeyError(f'Unknown table: {name}')
        mode = 'a' if self.workbook_path.exists() else 'w'
        kwargs = {'engine': 'openpyxl', 'mode': mode}
        if mode == 'a':
            kwargs['if_sheet_exists'] = 'replace'
        with pd.ExcelWriter(self.workbook_path, **kwargs) as writer:
            df.to_excel(writer, sheet_name=self.sheet_map[name], index=False)


@dataclass(frozen=True)
class CsvFolderAdapter:
    folder_path: Path

    def read_table(self, name: str) -> pd.DataFrame:
        path = self.folder_path / f'{name}.csv'
        if not path.exists():
            raise FileNotFoundError(f'CSV table not found: {path}')
        return pd.read_csv(path)

    def write_table(self, name: str, df: pd.DataFrame) -> None:
        self.folder_path.mkdir(parents=True, exist_ok=True)
        path = self.folder_path / f'{name}.csv'
        df.to_csv(path, index=False)


@dataclass(frozen=True)
class GoogleSheetsAdapterPlaceholder:
    spreadsheet_id: str

    def read_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError('Google Sheets adapter is planned but not enabled yet')

    def write_table(self, name: str, df: pd.DataFrame) -> None:
        raise NotImplementedError('Google Sheets adapter is planned but not enabled yet')
