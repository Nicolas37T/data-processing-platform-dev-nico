from models.conversion.Conversion_Base import Conversion_Base
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000124_01.

Report: Financiamiento Concedido por el Sistema Bancario por Bancos (BCB).
The sheet lists the financing balances by type of bank. The first column
holds the period: a year row opens each year and is followed by its
quarters (MAR, JUN, SEP, DIC). In the oldest years the quarterly rows
are hidden and the year row itself holds the year-end balance.
"""

import os
import re
import traceback
from datetime import date

import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import (
    last_day_month,
    month_abr_to_number,
    to_numeric_datax,
)

class D_BO_000000124_01(Conversion_Base):
    """Conversion robot for the bank financing by type of bank report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract the financing table and flatten it into melted format.

        Each header block becomes one level: a header shared by several
        columns (e.g. banks in operation) or a header separated from the
        column label by an empty row is ``nv1`` and the label below it is
        ``nv2``. Other columns keep their whole header in ``nv1``. Every
        period with figures is kept, hidden rows included, with the end
        date of its period.

        Args:
            file_path: Absolute path to the downloaded spreadsheet.
            key_words: Keywords that identify the report (not required,
                the table is located by its period column).
            template_path: Reference template path (not required).
            page_number: 1-based sheet index that holds the table.
            format: Output date format.

        Returns:
            A ``(metadata_dict, dataframe)`` tuple, or an empty string
            ``""`` if an unrecoverable error occurs.
        """
        try:
            file_name = os.path.basename(file_path)
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            sheets = workbook.worksheets
            sheet_index = int(page_number) - 1
            if not 0 <= sheet_index < len(sheets):
                sheet_index = 0
            sheet = sheets[sheet_index]
            date_column = sheet.min_column

            def clean_text(value):
                """Return the cell text with single spaces, or None."""
                if value is None:
                    return None
                return " ".join(str(value).split()) or None

            def is_number(value):
                """Tell whether a cell holds a number."""
                return isinstance(value, (int, float)) and not isinstance(
                    value, bool
                )

            def read_period(value):
                """Return the year and month written in a period cell.

                A year cell gives ``(year, None)``, a quarter label such as
                "SEP (1)" gives ``(None, 9)`` and "2025-MAR" gives both.
                """
                if is_number(value):
                    if float(value).is_integer() and 1900 <= value <= 2100:
                        return int(value), None
                    return None, None
                text = clean_text(value) or ""
                year_match = re.match(r"(\d{4})\b", text)
                month_match = re.search(r"[A-Za-z]{3}", text)
                year = int(year_match.group(1)) if year_match else None
                month = (
                    month_abr_to_number(month_match.group(0))
                    if month_match else None
                )
                return year, month

            # 1. Period rows and value columns (columns with numbers).
            period_rows = [
                row_index
                for row_index in range(1, sheet.max_row + 1)
                if any(read_period(sheet.cell(row_index, date_column).value))
            ]
            if not period_rows:
                raise ValueError("No period rows found in the sheet.")
            value_columns = [
                column_index
                for column_index in range(
                    date_column + 1, sheet.max_column + 1
                )
                if any(
                    is_number(sheet.cell(row_index, column_index).value)
                    for row_index in period_rows
                )
            ]
            if not value_columns:
                raise ValueError("No numeric columns found in the sheet.")

            # 2. Header rows: the block of text rows above the first
            #    period row (blank rows in between are skipped).
            def row_has_text(row_index):
                """Tell whether a row has text over the value columns."""
                return any(
                    clean_text(sheet.cell(row_index, column_index).value)
                    for column_index in value_columns
                )

            header_bottom = period_rows[0] - 1
            while header_bottom > 0 and not row_has_text(header_bottom):
                header_bottom -= 1
            header_top = header_bottom
            while header_top > 1 and row_has_text(header_top - 1):
                header_top -= 1
            if header_bottom < 1:
                raise ValueError("No header found above the periods.")
            header_rows = range(header_top, header_bottom + 1)

            # 3. Header text of each cell, whether it is shared by several
            #    value columns, and which header cells are occupied
            #    (merged cells occupy every cell they cover).
            header_map, occupied = {}, set()
            merged_tops = {}
            for merged in sheet.merged_cells.ranges:
                merged_tops[(merged.min_row, merged.min_col)] = merged
            covered_by_merge = set()
            for merged in merged_tops.values():
                for row_index in range(merged.min_row, merged.max_row + 1):
                    for column_index in range(
                        merged.min_col, merged.max_col + 1
                    ):
                        covered_by_merge.add((row_index, column_index))
            for row_index in header_rows:
                for column_index in range(
                    date_column + 1, sheet.max_column + 1
                ):
                    merged = merged_tops.get((row_index, column_index))
                    if merged is None and (
                        (row_index, column_index) in covered_by_merge
                    ):
                        continue
                    text = clean_text(
                        sheet.cell(row_index, column_index).value
                    )
                    if not text:
                        continue
                    last_row = merged.max_row if merged else row_index
                    last_column = merged.max_col if merged else column_index
                    columns = [
                        index for index in value_columns
                        if column_index <= index <= last_column
                    ]
                    for index in columns:
                        header_map[(row_index, index)] = (
                            text, len(columns) > 1
                        )
                        for row in range(row_index, last_row + 1):
                            occupied.add((row, index))

            # 4. Levels of each column: a new level starts when a shared
            #    header gives way to the column's own label, or when an
            #    empty header row separates two labels.
            column_levels = {}
            for column_index in value_columns:
                levels, lines = [], []
                last_shared, last_row = None, None
                for row_index in header_rows:
                    entry = header_map.get((row_index, column_index))
                    if entry:
                        text, shared = entry
                        has_gap = (
                            last_row is not None and last_row < row_index - 1
                        )
                        if lines and (shared != last_shared or has_gap):
                            levels.append(" ".join(lines))
                            lines = []
                        lines.append(text)
                        last_shared = shared
                    if (row_index, column_index) in occupied:
                        last_row = row_index
                if lines:
                    levels.append(" ".join(lines))
                # Asegurar que la columna de liquidación siempre tenga los 2 niveles
                full_header = " ".join(str(lvl) for lvl in levels if lvl)
                clean_hdr = re.sub(r"[-\s]+", "", full_header.upper())
                if "LIQUI" in full_header.upper() or "LIQUID" in clean_hdr:
                    levels = ["BANCOS", "BANCOS EN LIQUIDACIÓN"]
                column_levels[column_index] = levels
            depth = max(len(levels) for levels in column_levels.values())
            for levels in column_levels.values():
                levels.extend([None] * (depth - len(levels)))

            # 5. Titles: every text line printed above the table header.
            titles = []
            for row in sheet.iter_rows(min_row=1, max_row=header_top - 1):
                for cell in row:
                    text = clean_text(cell.value)
                    if text:
                        titles.append(text)
            if not titles:
                report_name = os.path.splitext(file_name)[0]
                report_name = re.sub(
                    r"\s+[A-Z]_[A-Z]{2}_\d+(?:_\d+)?$", "", report_name
                )
                titles = [" ".join(report_name.split())]

            # 6. Melt every period with figures. A year row opens the
            #    year; when it holds figures they are the year-end balance.
            records = []
            current_year = None
            for row_index in range(header_bottom + 1, sheet.max_row + 1):
                raw_cell = sheet.cell(row_index, date_column).value
                cell_text = clean_text(raw_cell) or ""
                if any(cell_text.upper().startswith(kw) for kw in ["FUENTE", "ELABORAC", "NOTA", "CUADRO"]):
                    break

                year, month = read_period(raw_cell)
                if year:
                    current_year = year
                values = [
                    sheet.cell(row_index, column_index).value
                    for column_index in value_columns
                ]
                if not any(is_number(value) for value in values):
                    continue
                if current_year is None or not (year or month):
                    continue
                month = month or 12
                cut_date = date(
                    current_year, month, last_day_month(current_year, month)
                ).strftime(format)
                for column_index, value in zip(value_columns, values):
                    records.append(
                        column_levels[column_index] + [cut_date, value]
                    )

            level_names = [f"nv{index}" for index in range(1, depth + 1)]
            dataframe = pd.DataFrame(
                records, columns=level_names + ["fecha", "valor"]
            )
            # Values are kept with two decimals, as the report format
            # requires.
            dataframe["valor"] = pd.to_numeric(
                dataframe["valor"], errors="coerce"
            ).round(2)

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number),
            }

            return metadata_dict, dataframe

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """Check the published totals against the sum of their parts.

        Two checks are made for every date, within ``TOLERANCE``:

        1. Group total: inside a group, the column labelled Total must
           equal the sum of the other columns of the group.
        2. Grand total: the TOTAL column must equal the sum of the other
           columns, taking each group through its own Total column.

        Args:
            dataframe: Melted DataFrame returned by ``extraction()``.
            decimal_separator: Decimal separator configured for the report.
            TOLERANCE: Allowed rounding difference.

        Returns:
            ``False`` when the data is valid; ``True`` when no value was
            extracted or a total does not match its parts.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            required = ["nv1", "nv2", "fecha", "valor"]
            if not set(required).issubset(dataframe.columns):
                return True

            data = dataframe[required].copy()
            data["valor"] = to_numeric_datax(
                data["valor"], decimal_separator
            )
            if data["valor"].dropna().empty:
                return True

            def has_total(text):
                """Tell whether a label holds the TOTAL pivot word."""
                return "TOTAL" in str(text).upper().split()

            # 1. Group totals.
            grouped = data[data["nv2"].notna()]
            for _, group in grouped.groupby(["nv1", "fecha"]):
                is_total = group["nv2"].map(has_total)
                totals = group.loc[is_total, "valor"].dropna()
                parts = group.loc[~is_total, "valor"].dropna()
                if totals.empty or parts.empty:
                    continue
                if abs(parts.sum() - totals.iloc[0]) > TOLERANCE:
                    return True

            # 2. Grand total.
            ungrouped = data.loc[data["nv2"].isna(), "nv1"]
            grand_labels = [
                label for label in dict.fromkeys(ungrouped)
                if has_total(label)
            ]
            if not grand_labels:
                return False
            grand = grand_labels[0]
            for _, rows in data.groupby("fecha"):
                is_grand = (rows["nv1"] == grand) & rows["nv2"].isna()
                total = rows.loc[is_grand, "valor"].dropna()
                if total.empty:
                    continue
                parts = []
                others = rows[rows["nv1"] != grand]
                for _, block in others.groupby("nv1", sort=False):
                    block_total = block["nv2"].map(has_total)
                    chosen = block[block_total] if block_total.any() else block
                    parts.extend(chosen["valor"].dropna())
                if parts and abs(sum(parts) - total.iloc[0]) > TOLERANCE:
                    return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Standard alias required by the platform and the test harness.

Executor_D_BO_000000124_01 = D_BO_000000124_01
Robot = D_BO_000000124_01
