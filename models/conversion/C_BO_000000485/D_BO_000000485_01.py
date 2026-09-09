"""Conversion robot for BCB fine gold quotations."""

import os
import re
import traceback

import pandas as pd
from unidecode import unidecode

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import (
    get_col_date,
    get_xlsx_report_dataframe,
    to_numeric_datax,
)


class D_BO_000000485_01(Conversion_Base):
    """Convert BCB fine gold quotations to the platform format."""

    def extraction(
        self,
        file_path,
        key_words,
        template_path,
        page_number,
        format="%Y-%m-%d",
    ):
        """Extract and normalize the BCB fine gold quotation table.

        Args:
            file_path (str): Absolute path to the source Excel file.
            key_words (str): Keywords configured for the report.
            template_path (str): Reserved template path required by the API.
            page_number (int): Initial worksheet number used for the search.
            format (str, optional): Output date format.

        Returns:
            tuple[dict, pd.DataFrame] | str: Report metadata and normalized
            data, or an empty string when extraction fails.
        """
        del template_path

        try:
            extension = os.path.splitext(file_path)[1].lower()
            if extension not in {".xls", ".xlsx"}:
                raise ValueError(f"Unsupported file extension: {extension}")

            normalized_keywords = unidecode(str(key_words or "")).lower()
            if normalized_keywords and "oro" not in normalized_keywords:
                raise ValueError("The configured keywords do not match gold.")

            report = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words="oro",
                page_number=page_number,
            )
            if not report:
                raise ValueError("The fine gold table was not found.")

            raw_dataframe, found_page_number = report
            raw_dataframe = raw_dataframe.dropna(
                how="all",
            ).dropna(
                how="all",
                axis=1,
            )

            header_index = None
            for row_index, row in raw_dataframe.iterrows():
                row_text = " ".join(
                    re.sub(r"\s+", " ", str(value)).strip()
                    for value in row.dropna()
                )
                normalized_row = unidecode(row_text).upper()
                if all(
                    term in normalized_row
                    for term in ("NRO", "FECHA", "ORO")
                ):
                    header_index = row_index
                    break

            if header_index is None:
                raise ValueError("The quotation header was not found.")

            headers = []
            for column_index, value in enumerate(
                raw_dataframe.loc[header_index]
            ):
                if pd.isna(value):
                    headers.append(f"column_{column_index}")
                else:
                    headers.append(
                        re.sub(r"\s+", " ", str(value)).strip()
                    )

            table = raw_dataframe.loc[header_index + 1:].copy()
            table.columns = headers
            table = table.dropna(how="all")

            normalized_headers = {
                header: unidecode(header).upper()
                for header in headers
            }
            number_column = next(
                (
                    header
                    for header, normalized in normalized_headers.items()
                    if normalized == "NRO"
                ),
                None,
            )
            date_column = next(
                (
                    header
                    for header, normalized in normalized_headers.items()
                    if normalized == "FECHA"
                ),
                None,
            )
            value_columns = [
                header
                for header, normalized in normalized_headers.items()
                if "ORO" in normalized
                and ("DOLAR" in normalized or " BS " in f" {normalized} ")
            ]

            if number_column is None or date_column is None:
                raise ValueError("Required identifier columns were not found.")
            if len(value_columns) != 2:
                raise ValueError(
                    "Expected two gold quotation columns, "
                    f"found {len(value_columns)}."
                )

            records = []
            for _, source_row in table.iterrows():
                number_value = source_row[number_column]
                date_value = source_row[date_column]
                if pd.isna(number_value) or pd.isna(date_value):
                    continue

                if (
                    isinstance(number_value, float)
                    and number_value.is_integer()
                ):
                    level_value = str(int(number_value))
                else:
                    level_value = str(number_value).strip()

                try:
                    report_date = pd.to_datetime(
                        date_value,
                        format=format,
                        errors="raise",
                    ).strftime(format)
                except (TypeError, ValueError):
                    normalized_date = get_col_date(str(date_value))
                    report_date = pd.to_datetime(
                        normalized_date,
                        format="%Y-%m-%d",
                        errors="raise",
                    ).strftime(format)

                for value_column in value_columns:
                    source_value = source_row[value_column]
                    if pd.isna(source_value):
                        raise ValueError(
                            f"Missing quotation value for row {level_value}."
                        )
                    records.append(
                        {
                            "nv1": value_column,
                            "nv2": level_value,
                            "fecha": report_date,
                            "valor": re.sub(
                                r"\s+",
                                " ",
                                str(source_value),
                            ).strip(),
                        }
                    )

            if not records:
                raise ValueError("No fine gold quotations were extracted.")

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": ["ORO COTIZACION"],
                "page_number": int(found_page_number),
            }
            dataframe = pd.DataFrame.from_records(
                records,
                columns=["nv1", "nv2", "fecha", "valor"],
            )
            return metadata, dataframe

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe,
        decimal_separator,
        TOLERANCE=6.0,
    ):
        """Validate numeric values from the fine gold quotation table.

        The report has no printed totals or averages to reconcile. Numeric
        conversion therefore completes the validation successfully.

        Args:
            dataframe (pd.DataFrame): Extracted report data.
            decimal_separator (str): Decimal separator used by the source.
            TOLERANCE (float, optional): Reserved validation tolerance.

        Returns:
            bool: True when validation fails, otherwise False.
        """
        del TOLERANCE

        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if "valor" not in dataframe.columns:
                return True

            source_values = dataframe["valor"]
            if source_values.isna().any():
                return True

            numeric_values = to_numeric_datax(
                source_values,
                decimal_separator,
            )
            return bool(numeric_values.isna().any())

        except Exception as error:
            print(f"Could not validate the fine gold report: {error}")
            return True


Robot = D_BO_000000485_01