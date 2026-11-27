from models.conversion.Conversion_Base import Conversion_Base
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000271_01.

Report: FIFA Men's World Ranking. The spreadsheet lists one team per
row with its ranking position, recent results and the published numeric
measures (points and, when available, the variation of the last result).
The set of columns changes between publications, so every column is
classified from its content instead of fixed positions or names.
"""

import os
import re
import traceback

import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000271_01(Conversion_Base):
    """Conversion robot for the FIFA Men's World Ranking report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract the ranking table and flatten it into melted format.

        Each team row produces one record per published measure: the
        first levels hold the descriptive cells (position, team, results),
        the next level holds the measure header, the last level holds the
        qualifier printed next to the number (sign or asterisk) and
        ``valor`` holds the number itself. Rows without any published
        measure (e.g. unranked teams) are kept as one record with an
        empty value.

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

            date_pattern = re.compile(
                r"^(\d{4}-\d{2}-\d{2})(?:[ T]00:00:00)?$"
            )
            measure_pattern = re.compile(r"^([+-]?)(\d+[.,]\d+)(\**)$")

            def clean_text(value):
                """Return the cell text without line breaks, or None."""
                if pd.isna(value):
                    return None
                text = re.sub(r"[\r\n]+", "", str(value)).strip()
                return text or None

            # 1. The header is the row right above the first dated row.
            first_data_row = None
            for row_index in range(len(sheet)):
                cells = sheet.iloc[row_index].dropna().str.strip()
                if cells.str.match(date_pattern).any():
                    first_data_row = row_index
                    break
            if not first_data_row:
                raise ValueError("No dated rows found below a header row.")
            header = sheet.iloc[first_data_row - 1]
            body = sheet.iloc[first_data_row:]

            # 2. Titles: the official report name (the sheet has no title
            #    rows), followed by any text line printed above the header.
            titles = ["Ranking Masculino"]
            for row_index in range(first_data_row - 1):
                for value in sheet.iloc[row_index].dropna():
                    text = " ".join(str(value).split())
                    if text:
                        titles.append(text)

            # 3. Classify every column from its content: one date column,
            #    numeric measure columns and descriptive level columns.
            date_column = None
            measure_columns = []
            for column in sheet.columns:
                cells = body[column].dropna().str.strip()
                cells = cells[cells != ""]
                if cells.empty:
                    continue
                is_date = cells.str.match(date_pattern).all()
                if date_column is None and is_date:
                    date_column = column
                elif cells.str.match(measure_pattern).all():
                    measure_columns.append(column)
            if date_column is None or not measure_columns:
                raise ValueError("Date or measure columns not found.")

            # Descriptive levels sit between the date column and the first
            # measure. Only columns with actual data are kept so all-null
            # level columns are not generated.
            first_measure = min(measure_columns)
            level_columns = [
                column for column in sheet.columns
                if date_column < column < first_measure
                and not body[column].dropna().str.strip().replace("", pd.NA).dropna().empty
            ]

            # 4. Detect the decimal mark used by the source numbers.
            measure_cells = pd.concat(
                [body[column].dropna() for column in measure_columns]
            )
            uses_comma = measure_cells.str.contains(",").any()
            decimal_mark = "," if uses_comma else "."

            # 5. Melt every measure of every team row into one record.
            records = []
            for _, row in body.iterrows():
                date_text = clean_text(row[date_column]) or ""
                date_match = date_pattern.match(date_text)
                if not date_match:
                    continue
                cut_date = pd.to_datetime(
                    date_match.group(1), format="%Y-%m-%d"
                ).strftime(format)
                levels = [clean_text(row[column]) for column in level_columns]

                measures_found = False
                for column in measure_columns:
                    measure_match = measure_pattern.match(
                        clean_text(row[column]) or ""
                    )
                    if not measure_match:
                        continue
                    measures_found = True
                    sign, number, mark = measure_match.groups()
                    records.append(
                        levels
                        + [
                            clean_text(header[column]),
                            (sign + mark) or None,
                            cut_date,
                            number,
                        ]
                    )

                # Rows without any published measure (e.g. unranked
                # teams) are kept so every team in the file is extracted.
                if not measures_found:
                    records.append(levels + [None, None, cut_date, None])

            level_names = [
                f"nv{index}" for index in range(1, len(level_columns) + 3)
            ]
            dataframe = pd.DataFrame(
                records, columns=level_names + ["fecha", "valor"]
            )
            dataframe["valor"] = to_numeric_datax(
                dataframe["valor"], decimal_separator=decimal_mark
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
        """Check the integrity of the extracted measures.

        The ranking publishes no totals or averages to reconcile, so the
        validation confirms that every published ``valor`` is numeric
        once it is normalized with ``decimal_separator``.

        Args:
            dataframe: Melted DataFrame returned by ``extraction()``.
            decimal_separator: Decimal separator configured for the report.
            TOLERANCE: Allowed rounding difference (no totals to compare).

        Returns:
            ``False`` when the data is valid; ``True`` when no value was
            extracted or a published value is not numeric.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if "valor" not in dataframe.columns:
                return True
            # Rows without a published measure carry no value, so only
            # the published values are checked.
            values = dataframe["valor"].dropna()
            if values.empty:
                return True
            numeric_values = to_numeric_datax(values, decimal_separator)
            return bool(numeric_values.isna().any())

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Standard alias required by the platform and the test harness.

Executor_D_BO_000000271_01 = D_BO_000000271_01
Robot = D_BO_000000271_01
