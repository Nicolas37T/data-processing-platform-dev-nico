from models.conversion.Conversion_Base import Conversion_Base
"""Convert Trinidad's monthly consumer price variation report."""

import os
import re
import traceback
from numbers import Real

import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import (
    get_xlsx_report_dataframe,
    search_key_words,
    to_numeric_datax,
)
from models.download.tools.download_tools import month_abr_to_number, month_to_number


class D_BO_000000016_01(Conversion_Base):
    """Extract Trinidad's monthly IPC variation by division."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "division ciudad",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return report metadata and monthly variation observations.

        The table, header rows, divisions, years and months are detected from
        the workbook content. Dates represent the last day of each month.
        Values retain the report's percentage points and factor 1.
        """
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The initial sheet number must be positive.")

            search_terms = re.sub(
                r"\s+", " ", key_words or "division ciudad"
            ).strip().lower()
            if search_terms == "division ciudad":
                search_terms = (
                    "trinidad variacion porcentual mensual indice precios "
                    "consumidor segun division ~acumulada"
                )
            report = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=search_terms,
                page_number=page_number,
            )
            if report is None:
                raise ValueError(
                    "Trinidad's monthly IPC variation table was not found."
                )
            raw_data, found_page = report

            title_mask = raw_data.map(
                lambda value: isinstance(value, str)
                and search_key_words(
                    value,
                    "trinidad variacion porcentual mensual indice precios "
                    "consumidor segun division ~acumulada",
                )
            )
            title_locations = np.argwhere(title_mask.to_numpy())
            if len(title_locations) != 1:
                raise ValueError("A unique Trinidad report title is required.")
            title_row = int(title_locations[0][0])

            header_row = None
            code_column = None
            label_column = None
            for row_index in range(title_row + 1, len(raw_data)):
                row = raw_data.iloc[row_index]
                division_columns = [
                    int(column)
                    for column, value in row.items()
                    if isinstance(value, str)
                    and search_key_words(value.strip(), "division", True)
                ]
                description_columns = [
                    int(column)
                    for column, value in row.items()
                    if isinstance(value, str)
                    and search_key_words(value.strip(), "descripcion", True)
                ]
                if division_columns and description_columns:
                    header_row = row_index
                    code_column = division_columns[0]
                    label_column = description_columns[0]
                    break
            if header_row is None or label_column <= code_column:
                raise ValueError("The division headers were not found.")

            titles = []
            title_start = max(0, title_row - 1)
            for _, row in raw_data.iloc[title_start:header_row].iterrows():
                parts = [
                    re.sub(r"\s+", " ", value).strip()
                    for value in row
                    if isinstance(value, str) and value.strip()
                ]
                title = " ".join(dict.fromkeys(parts))
                if title and title not in titles:
                    titles.append(title)
            if not titles:
                raise ValueError("The report titles were not found.")

            month_row = header_row + 1
            first_row = None
            for row_index in range(month_row + 1, len(raw_data)):
                code = str(raw_data.iat[row_index, code_column]).strip()
                label = raw_data.iat[row_index, label_column]
                if (
                    re.fullmatch(r"0(?:\.0+)?", code)
                    and isinstance(label, str)
                    and search_key_words(label.strip(), "indice general", True)
                ):
                    first_row = row_index
                    break
            if first_row is None:
                raise ValueError("The INDICE GENERAL row was not found.")

            row_indices = []
            division_codes = set()
            for row_index in range(first_row, len(raw_data)):
                code = raw_data.iat[row_index, code_column]
                label = raw_data.iat[row_index, label_column]
                numeric_code = pd.to_numeric(
                    pd.Series([code]), errors="coerce"
                ).iloc[0]
                if pd.isna(numeric_code):
                    break
                if not float(numeric_code).is_integer():
                    raise ValueError("A division code is not an integer.")
                if not isinstance(label, str) or not label.strip():
                    raise ValueError("A division description is missing.")
                division_code = int(numeric_code)
                if division_code in division_codes:
                    raise ValueError("Duplicate division codes exist.")
                division_codes.add(division_code)
                row_indices.append(row_index)
            if not row_indices or min(division_codes) != 0:
                raise ValueError("No valid division records were found.")

            date_columns = {}
            current_year = None
            for column in range(label_column + 1, raw_data.shape[1]):
                year_label = str(raw_data.iat[header_row, column]).strip()
                year_match = re.search(r"\b((?:19|20)\d{2})\b", year_label)
                if year_match:
                    current_year = int(year_match.group(1))

                month_label = raw_data.iat[month_row, column]
                month_name = re.sub(
                    r"\s+", " ", str(month_label)
                ).strip(" .-/_")
                month = (
                    month_to_number(month_name)
                    or month_abr_to_number(month_name)
                )
                if month is None:
                    values = raw_data.loc[row_indices, column]
                    if values.notna().any():
                        raise ValueError(
                            f"Unrecognized monthly header: {month_label}."
                        )
                    continue
                if current_year is None:
                    raise ValueError("A month has no associated year.")
                month_date = pd.Timestamp(current_year, month, 1)
                date_columns[column] = (
                    month_date + pd.offsets.MonthEnd(0)
                ).strftime(format)

            if not date_columns or len(set(date_columns.values())) != len(
                date_columns
            ):
                raise ValueError("Monthly columns are missing or duplicated.")

            table = raw_data.loc[row_indices, list(date_columns)].copy()
            table = table.rename(columns=date_columns)
            labels = raw_data.loc[row_indices, label_column].map(
                lambda value: re.sub(r"\s+", " ", value).strip()
            )
            table.insert(0, "nv1", labels.to_list())
            dataframe = table.melt(
                id_vars=["nv1"],
                var_name="fecha",
                value_name="valor",
            )

            values = dataframe["valor"]
            numeric_mask = values.map(
                lambda value: isinstance(value, Real)
                and not isinstance(value, (bool, np.bool_))
            )
            missing_mask = values.isna() | values.astype(str).str.strip().isin(
                ["", "-", "..", "..."]
            )
            if missing_mask.any():
                raise ValueError("A monthly division value is missing.")
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], ","
            )
            if numeric.isna().any() or not np.isfinite(numeric).all():
                raise ValueError(
                    "A variation value is not finite numeric data."
                )
            dataframe["valor"] = numeric.round(2)
            if dataframe.duplicated(["nv1", "fecha"]).any():
                raise ValueError("Duplicate monthly division records exist.")

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(found_page),
            }
            return metadata, dataframe
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
        """Return True when structure, dates or numeric values are invalid.

        Monthly percentage changes by division are not additive totals, so
        the general variation cannot be reconciled by summing divisions.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if decimal_separator not in {",", "."}:
                return True
            columns = ["nv1", "fecha", "valor"]
            if not set(columns).issubset(dataframe.columns):
                return True
            data = dataframe[columns]
            if not data[["nv1", "fecha"]].map(
                lambda value: isinstance(value, str)
            ).all().all():
                return True
            if data["nv1"].str.strip().isin(["", "-"]).any():
                return True
            if data.duplicated(["nv1", "fecha"]).any():
                return True

            dates = pd.to_datetime(
                data["fecha"], format="%Y-%m-%d", errors="coerce"
            )
            if dates.isna().any() or not dates.dt.is_month_end.all():
                return True
            unique_dates = pd.DatetimeIndex(sorted(dates.unique()))
            expected_dates = pd.date_range(
                unique_dates.min(), unique_dates.max(), freq="ME"
            )
            if not unique_dates.equals(expected_dates):
                return True

            division_sets = data.groupby("fecha")["nv1"].agg(frozenset)
            if len(set(division_sets)) != 1:
                return True

            values = data["valor"]
            numeric_mask = values.map(
                lambda value: isinstance(value, Real)
                and not isinstance(value, (bool, np.bool_))
            )
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask & values.notna()
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], decimal_separator
            )
            return bool(
                numeric.isna().any() or not np.isfinite(numeric).all()
            )
        except Exception as error:
            print(f"Could not validate Trinidad's IPC variation: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000016_01

Executor_D_BO_000000016_01 = D_BO_000000016_01
Robot = D_BO_000000016_01
