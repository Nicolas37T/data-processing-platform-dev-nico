from models.conversion.Conversion_Base import Conversion_Base
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000103_01.

Report: Origen de la Liquidez Total (BCB). The sheet holds one row per
period (a year for the oldest rows and a month for the rest) and one
column per component of the total liquidity. Some columns share a group
header printed above them (the net credit to the public sector) and the
last column holds the total liquidity.
"""

import os
import re
import traceback
from datetime import date
from itertools import combinations

import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import last_day_month, to_numeric_datax

class D_BO_000000103_01(Conversion_Base):
    """Conversion robot for the origin of total liquidity report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract the liquidity table and flatten it into melted format.

        A column under a group header (e.g. the net credit to the public
        sector) keeps the group in ``nv1`` and its own header in ``nv2``.
        Any other column keeps its whole header in ``nv1`` and ``nv2``
        stays empty. Every cell of the table is kept, including the empty
        ones, with the end date of its period.

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

            def clean_text(value):
                """Return the cell text with single spaces, or None.

                Words printed with spaced letters (e.g. "T O T A L") are
                joined back into one word.
                """
                if value is None:
                    return None
                words = []
                for chunk in re.split(r"\s{2,}", str(value).strip()):
                    tokens = chunk.split()
                    if len(tokens) > 1 and all(len(t) == 1 for t in tokens):
                        words.append("".join(tokens))
                    else:
                        words.extend(tokens)
                return " ".join(words) or None

            def to_cut_date(value):
                """Return the period end date of a period cell, or None."""
                if isinstance(value, date):
                    year, month = value.year, value.month
                elif (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and float(value).is_integer()
                    and 1900 <= value <= 2100
                ):
                    year, month = int(value), 12
                else:
                    return None
                day = last_day_month(year, month)
                return date(year, month, day).strftime(format)

            def join_lines(lines):
                """Join header lines, dropping a word repeated at a break."""
                words = []
                for line in lines:
                    line_words = line.split()
                    if (
                        words
                        and line_words
                        and words[-1].lower() == line_words[0].lower()
                    ):
                        line_words = line_words[1:]
                    words.extend(line_words)
                return " ".join(words) or None

            # 1. Data rows: rows whose first column holds a period.
            date_column = sheet.min_column
            data_rows = [
                row_index
                for row_index in range(1, sheet.max_row + 1)
                if to_cut_date(sheet.cell(row_index, date_column).value)
            ]
            if not data_rows:
                raise ValueError("No period rows found in the sheet.")
            first_row = data_rows[0]

            # 2. Value columns: columns with at least one number.
            value_columns = [
                column_index
                for column_index in range(
                    date_column + 1, sheet.max_column + 1
                )
                if any(
                    isinstance(sheet.cell(row_index, column_index).value,
                               (int, float))
                    for row_index in data_rows
                )
            ]
            if not value_columns:
                raise ValueError("No numeric columns found in the sheet.")

            # 3. Header rows: the block of text rows right above the
            #    first period row.
            def row_has_text(row_index):
                """Tell whether a row has text over the value columns."""
                return any(
                    clean_text(sheet.cell(row_index, column_index).value)
                    for column_index in value_columns
                )

            header_top = first_row
            while header_top > 1 and row_has_text(header_top - 1):
                header_top -= 1
            header_rows = range(header_top, first_row)

            # 4. Header text of each cell and whether it is shared by
            #    several value columns (merged or centered across them).
            merged_lookup = {}
            for merged in sheet.merged_cells.ranges:
                for row_index in range(merged.min_row, merged.max_row + 1):
                    for column_index in range(
                        merged.min_col, merged.max_col + 1
                    ):
                        merged_lookup[(row_index, column_index)] = merged

            header_map = {}
            for row_index in header_rows:
                for column_index in range(
                    date_column + 1, sheet.max_column + 1
                ):
                    cell = sheet.cell(row_index, column_index)
                    merged = merged_lookup.get((row_index, column_index))
                    if merged is not None:
                        if (merged.min_row, merged.min_col) != (
                            row_index, column_index
                        ):
                            continue
                        last_column = merged.max_col
                    else:
                        last_column = column_index
                        if cell.alignment.horizontal == "centerContinuous":
                            while (
                                last_column < sheet.max_column
                                and sheet.cell(
                                    row_index, last_column + 1
                                ).value is None
                                and sheet.cell(
                                    row_index, last_column + 1
                                ).alignment.horizontal == "centerContinuous"
                            ):
                                last_column += 1
                    text = clean_text(cell.value)
                    if not text:
                        continue
                    covered = [
                        index for index in value_columns
                        if column_index <= index <= last_column
                    ]
                    for index in covered:
                        header_map[(row_index, index)] = (
                            text, len(covered) > 1
                        )

            # 5. Levels of each column: a shared header is the group
            #    (nv1) and the column's own lines its label (nv2).
            column_levels = {}
            for column_index in value_columns:
                group_lines, own_lines = [], []
                for row_index in header_rows:
                    text, shared = header_map.get(
                        (row_index, column_index), (None, False)
                    )
                    if text:
                        (group_lines if shared else own_lines).append(text)
                if group_lines:
                    levels = [join_lines(group_lines), join_lines(own_lines)]
                else:
                    levels = [join_lines(own_lines), None]
                column_levels[column_index] = levels

            # 6. Titles: every text line printed above the table header.
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

            # 7. Melt every cell of the table into one record.
            records = []
            for row_index in data_rows:
                cut_date = to_cut_date(
                    sheet.cell(row_index, date_column).value
                )
                for column_index, levels in column_levels.items():
                    value = sheet.cell(row_index, column_index).value
                    records.append(levels + [cut_date, value])

            dataframe = pd.DataFrame(
                records, columns=["nv1", "nv2", "fecha", "valor"]
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

        1. Group total: inside a group, the column labelled TOTAL must
           equal the sum of the other columns of the group.
        2. Grand total: the last column labelled TOTAL outside a group
           must equal the sum of the other top level columns (columns
           outside a group plus the group totals). When a column is the
           difference of two previous ones (e.g. net = gross - debts),
           only the net column enters the sum.

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

            # 2. Grand total over the top level columns.
            is_top = data["nv2"].isna() | data["nv2"].map(has_total)
            top = data[is_top].copy()
            top["series"] = top["nv1"].where(
                top["nv2"].isna(), top["nv1"] + " / " + top["nv2"]
            )
            order = list(dict.fromkeys(top["series"]))
            table = top.pivot_table(
                index="fecha", columns="series", values="valor",
                aggfunc="first", dropna=False,
            ).reindex(columns=order)

            ungrouped = list(dict.fromkeys(data.loc[
                data["nv2"].isna(), "nv1"
            ]))
            grand_totals = [label for label in ungrouped if has_total(label)]
            if not grand_totals:
                return False
            grand = grand_totals[-1]
            components = [label for label in order if label != grand]

            # A column equal to the difference of two previous columns
            # replaces them in the sum (e.g. net = gross - debts).
            replaced = set()
            for gross, minus, net in combinations(components, 3):
                rows = table[[gross, minus, net]].dropna()
                if rows.empty:
                    continue
                gap = rows[gross] - rows[minus] - rows[net]
                if (gap.abs() <= TOLERANCE).all():
                    replaced.update({gross, minus})

            parts = [label for label in components if label not in replaced]
            rows = table[parts + [grand]].dropna()
            if rows.empty:
                return True
            gap = rows[parts].sum(axis=1) - rows[grand]
            return bool((gap.abs() > TOLERANCE).any())

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Standard alias required by the platform and the test harness.

Executor_D_BO_000000103_01 = D_BO_000000103_01
Robot = D_BO_000000103_01
