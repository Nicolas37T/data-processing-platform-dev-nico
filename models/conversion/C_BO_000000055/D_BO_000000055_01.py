from models.conversion.Conversion_Base import Conversion_Base
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000055_01.

Report: Ubicacion de Puntos de Atencion de Entidades Financieras. The
spreadsheet is assembled from several filtered queries: each block starts
with a ``Fecha: DD-MM-YYYY`` line, followed by the column header and one
row per service point (location, entity, point type, point name, address,
phones, schedules, etc.). The report publishes no figures, so every
service point row is counted as one.
"""

import os
import re
import traceback

import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000055_01(Conversion_Base):
    """Conversion robot for the financial service points location report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract every service point row and flatten it into melted format.

        The first four table columns (location, entity name, point type
        and point name) become ``nv1`` to ``nv4``. Each row takes the date
        of the ``Fecha`` line that opens its block, and ``valor`` is 1
        because every row is one service point. Every row of the file is
        kept in its original order; only the repeated header and date
        lines are skipped.

        Args:
            file_path: Absolute path to the downloaded spreadsheet.
            key_words: Keywords that identify the report (the source has
                a single sheet, so the table is located by page_number).
            template_path: Reference template path (not required).
            page_number: 1-based sheet index that holds the table.
            format: Output date format.

        Returns:
            A ``(metadata_dict, dataframe)`` tuple, or an empty string
            ``""`` if an unrecoverable error occurs.
        """
        try:
            file_name = os.path.basename(file_path)
            sheet_index = max(int(page_number) - 1, 0)
            sheet = pd.read_excel(
                file_path, sheet_name=sheet_index, header=None, dtype=str
            )

            # Number of identifying columns kept as levels (location,
            # entity, point type and point name), as the report format
            # requires.
            level_count = 4
            date_line_pattern = (
                r"(?i)^fecha\s*:\s*(\d{1,2})[-/](\d{1,2})[-/](\d{4})$"
            )
            placeholder_pattern = re.compile(r"^Unnamed: \d+$")

            def clean_text(value):
                """Return the cell text with single spaces, or None."""
                if pd.isna(value):
                    return None
                text = " ".join(str(value).split())
                return text or None

            levels = sheet.iloc[:, :level_count].apply(
                lambda column: column.map(clean_text)
            )

            # 1. Date lines ("Fecha: DD-MM-YYYY") open every block.
            date_parts = levels.iloc[:, 0].str.extract(date_line_pattern)
            is_date_line = date_parts[0].notna()
            if not is_date_line.any():
                raise ValueError("No 'Fecha' line found in the sheet.")

            row_dates = pd.Series(None, index=sheet.index, dtype=object)
            for row_index in is_date_line[is_date_line].index:
                day, month, year = date_parts.loc[row_index]
                row_dates[row_index] = pd.Timestamp(
                    int(year), int(month), int(day)
                ).strftime(format)
            row_dates = row_dates.ffill()

            # 2. Locate the column header: search for the row below
            #    the date line that holds the column names.
            first_date_row = is_date_line[is_date_line].index[0]
            header_row = None
            for row_index in range(first_date_row + 1, len(sheet)):
                row_vals = [str(v).lower() for v in levels.iloc[row_index].dropna()]
                if any("departamento" in v for v in row_vals):
                    header_row = row_index
                    break
                if levels.iloc[row_index].notna().any() and header_row is None:
                    header_row = row_index
            if header_row is None:
                raise ValueError("No header row found below 'Fecha'.")

            header = levels.loc[header_row].fillna("")
            is_header = levels.fillna("").eq(header, axis=1).all(axis=1)
            is_header_text = levels.iloc[:, 0].astype(str).str.lower().str.contains("departamento", na=False)

            # 3. Titles: the sheet has no title rows, so titulo1 is the
            #    report name taken from the file name (date prefix and
            #    report code removed), followed by the text lines printed
            #    above the first header (e.g. the cut-off date line).
            report_name = os.path.splitext(file_name)[0]
            report_name = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", report_name)
            report_name = re.sub(
                r"\s+[A-Z]_[A-Z]{2}_\d+(?:_\d+)?$", "", report_name
            )
            report_name = " ".join(report_name.split()).capitalize()
            titles = [report_name] if report_name else []
            for row_index in range(header_row):
                for value in sheet.iloc[row_index].dropna():
                    text = clean_text(value)
                    if text and not placeholder_pattern.match(text):
                        titles.append(text)

            # 4. Data rows: every row below the first header that is not a
            #    repeated date line or header and has level text.
            is_data = (
                (sheet.index > header_row)
                & ~is_date_line
                & ~is_header
                & ~is_header_text
                & levels.notna().any(axis=1)
            )
            dataframe = levels[is_data].copy()
            dataframe.columns = [
                f"nv{index}" for index in range(1, level_count + 1)
            ]
            dataframe["fecha"] = row_dates[is_data]
            # The report publishes no figures: each row is one point.
            dataframe["valor"] = 1
            dataframe = dataframe.reset_index(drop=True)

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
        """Check the integrity of the extracted service point counts.

        The report publishes no totals to reconcile, so the validation
        confirms that every row has a cut-off date and a numeric
        ``valor`` once it is normalized with ``decimal_separator``.

        Args:
            dataframe: Melted DataFrame returned by ``extraction()``.
            decimal_separator: Decimal separator configured for the report.
            TOLERANCE: Allowed rounding difference (no totals to compare).

        Returns:
            ``False`` when the data is valid; ``True`` when no row was
            extracted, a date is missing or a value is not numeric.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if not {"fecha", "valor"}.issubset(dataframe.columns):
                return True
            if dataframe["fecha"].isna().any():
                return True
            numeric_values = to_numeric_datax(
                dataframe["valor"], decimal_separator
            )
            return bool(numeric_values.isna().any())

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Standard alias required by the platform and the test harness.

Executor_D_BO_000000055_01 = D_BO_000000055_01
Robot = D_BO_000000055_01
