from models.conversion.Conversion_Base import Conversion_Base
# Pega aquí el código del pasante o cárgalo desde GitHub...
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000101_02.

Report: Base Monetaria - Destino. The sheet holds the monetary base table
with two column blocks under a shared header: ORIGEN and DESTINO. This
robot extracts the DESTINO block (currency held by the public and bank
reserves by currency). The first column holds the period: a year for the
annual rows and a month for the monthly rows.
"""

import os
import re
import traceback
from datetime import date

import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import last_day_month, to_numeric_datax

class D_BO_000000101_02(Conversion_Base):
    """Conversion robot for the monetary base by destination report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract the DESTINO block and flatten it into melted format.

        ``nv1`` is the block header (DESTINO), ``nv2`` the column group
        (e.g. bank reserves) and ``nv3`` the column label inside the group
        (MN, UFV, ME, TOTAL). A column without a group keeps its whole
        header in ``nv2`` and ``nv3`` stays empty. Every cell of the block
        is kept, including the empty ones, with its period end date.

        Args:
            file_path: Absolute path to the downloaded spreadsheet.
            key_words: Keywords that identify the report (not required,
                the block is located by its header cell).
            template_path: Reference template path (not required).
            page_number: 1-based sheet index checked first.
            format: Output date format.

        Returns:
            A ``(metadata_dict, dataframe)`` tuple, or an empty string
            ``""`` if an unrecoverable error occurs.
        """
        try:
            file_name = os.path.basename(file_path)
            workbook = openpyxl.load_workbook(file_path, data_only=True)

            # Pivot cell that opens the destination block of the table.
            anchor_text = "DESTINO"

            def clean_text(value):
                """Return the cell text with single spaces, or None."""
                if value is None:
                    return None
                text = " ".join(str(value).split())
                return text or None

            def compact(value):
                """Return the cell text without spaces, in upper case."""
                return re.sub(r"\s+", "", str(value or "")).upper()

            def to_cut_date(value):
                """Return the period end date of a period cell, or None."""
                if isinstance(value, date):
                    year, month = value.year, value.month
                elif (
                    isinstance(value, (int, float))
                    and float(value).is_integer()
                    and 1900 <= value <= 2100
                ):
                    year, month = int(value), 12
                else:
                    return None
                day = last_day_month(year, month)
                return date(year, month, day).strftime(format)

            def join_lines(lines):
                """Join header lines, rejoining words split by a hyphen."""
                text = ""
                for line in lines:
                    if text.endswith("-"):
                        text = text[:-1] + line
                    else:
                        text = f"{text} {line}".strip()
                return text or None

            # 1. Locate the anchor cell, checking the requested sheet first.
            sheets = workbook.worksheets
            preferred = int(page_number) - 1
            if not 0 <= preferred < len(sheets):
                preferred = 0
            ordered = [sheets[preferred]] + [
                sheet for index, sheet in enumerate(sheets)
                if index != preferred
            ]
            matches = (
                (sheet, cell)
                for sheet in ordered
                for row in sheet.iter_rows()
                for cell in row
                if compact(cell.value) == anchor_text
            )
            sheet, anchor = next(matches, (None, None))
            if anchor is None:
                raise ValueError("DESTINO block not found in the file.")

            merged_lookup = {}
            for merged in sheet.merged_cells.ranges:
                for row_index in range(merged.min_row, merged.max_row + 1):
                    for column_index in range(
                        merged.min_col, merged.max_col + 1
                    ):
                        merged_lookup[(row_index, column_index)] = merged

            def header_cell(row_index, column_index):
                """Return the header text and whether it spans columns.

                A merged cell shares its text with every column it covers;
                its text is read once, on the first row of the merge.
                """
                merged = merged_lookup.get((row_index, column_index))
                if merged is None:
                    value = sheet.cell(row_index, column_index).value
                    return clean_text(value), False
                if row_index != merged.min_row:
                    return None, False
                value = sheet.cell(merged.min_row, merged.min_col).value
                return clean_text(value), merged.max_col > merged.min_col

            # 2. The block spans the columns covered by the anchor cell.
            block = merged_lookup.get((anchor.row, anchor.column))
            first_column = block.min_col if block else anchor.column
            last_column = block.max_col if block else anchor.column
            nv1 = clean_text(anchor.value)

            # 3. Data rows: rows below the anchor whose first column holds
            #    a period (year or month). The rows in between are headers.
            date_column = sheet.min_column
            data_rows = [
                row_index
                for row_index in range(anchor.row + 1, sheet.max_row + 1)
                if to_cut_date(sheet.cell(row_index, date_column).value)
            ]
            if not data_rows:
                raise ValueError("No period rows found below the header.")
            header_rows = range(anchor.row + 1, data_rows[0])

            # 4. Levels of each column: header lines shared by several
            #    columns form the group (nv2); the column's own lines form
            #    its label (nv3). Without a group, the own lines are nv2.
            column_levels = {}
            for column_index in range(first_column, last_column + 1):
                group_lines, own_lines = [], []
                for row_index in header_rows:
                    text, shared = header_cell(row_index, column_index)
                    if text:
                        (group_lines if shared else own_lines).append(text)
                if group_lines:
                    levels = [join_lines(group_lines), join_lines(own_lines)]
                else:
                    levels = [join_lines(own_lines), None]
                column_levels[column_index] = levels

            # 5. Titles: every text line printed above the block header.
            titles = []
            for row in sheet.iter_rows(min_row=1, max_row=anchor.row - 1):
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

            # 6. Melt every cell of the block into one record.
            records = []
            for row_index in data_rows:
                cut_date = to_cut_date(
                    sheet.cell(row_index, date_column).value
                )
                for column_index, levels in column_levels.items():
                    value = sheet.cell(row_index, column_index).value
                    records.append([nv1] + levels + [cut_date, value])

            dataframe = pd.DataFrame(
                records, columns=["nv1", "nv2", "nv3", "fecha", "valor"]
            )
            dataframe["valor"] = pd.to_numeric(
                dataframe["valor"], errors="coerce"
            )

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
        """Check that every group total matches the sum of its parts.

        For each group with column labels (e.g. bank reserves) and date,
        the TOTAL column must equal the sum of the other columns (MN,
        UFV, ME) within ``TOLERANCE``. Dates where the breakdown is not
        published (empty or all zeros) have nothing to reconcile.

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
            required = {"nv1", "nv2", "nv3", "fecha", "valor"}
            if not required.issubset(dataframe.columns):
                return True

            data = dataframe.copy()
            data["valor"] = to_numeric_datax(
                data["valor"], decimal_separator
            )
            if data["valor"].dropna().empty:
                return True

            grouped = data[data["nv3"].notna()]
            is_total = grouped["nv3"].str.strip().str.upper().eq("TOTAL")
            for _, group in grouped.groupby(["nv1", "nv2", "fecha"]):
                group_total = is_total.loc[group.index]
                totals = group.loc[group_total, "valor"].dropna()
                parts = group.loc[~group_total, "valor"].dropna()
                if totals.empty or parts.empty or (parts == 0).all():
                    continue
                if abs(parts.sum() - totals.iloc[0]) > TOLERANCE:
                    return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Standard alias required by the platform and the test harness.

Executor_D_BO_000000101_02 = D_BO_000000101_02
Robot = D_BO_000000101_02
