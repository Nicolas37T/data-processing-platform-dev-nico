from models.conversion.Conversion_Base import Conversion_Base
"""Convert monthly consumer price variation for all reported cities."""

import os
import re
import traceback
from numbers import Real

import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, to_numeric_datax
from models.download.tools.download_tools import month_abr_to_number, month_to_number


class D_BO_000000016_01(Conversion_Base):
    """Extract monthly IPC variation by city and division."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "division ciudad",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return consolidated observations from the nine city sheets.

        Report sheets, titles, divisions, years and months are detected from
        workbook content. Dates represent the last day of each month, and
        values retain the report's percentage points and factor 1.
        """
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The page number must be positive.")

            search_terms = re.sub(
                r"\s+", " ", key_words or "division ciudad"
            ).strip().lower()
            default_ignored_terms = []
            if search_terms == "division ciudad":
                search_terms = (
                    "variacion porcentual mensual indice precios consumidor "
                    "segun division"
                )
                default_ignored_terms = ["acumulado", "acumulada"]
            search_tokens = search_terms.split()
            ignored_terms = default_ignored_terms + [
                token[1:] for token in search_tokens if token.startswith("~")
            ]
            positive_terms = " ".join(
                token for token in search_tokens if not token.startswith("~")
            )

            sheets = pd.read_excel(file_path, sheet_name=None, header=None)
            city_frames = []
            city_names = set()
            reference_divisions = None
            reference_dates = None
            report_title = None
            unit_title = None

            for raw_data in sheets.values():
                title_mask = raw_data.map(
                    lambda value: isinstance(value, str)
                    and search_key_words(value, positive_terms)
                    and not any(
                        search_key_words(value, term)
                        for term in ignored_terms
                    )
                )
                title_locations = np.argwhere(title_mask.to_numpy())
                if len(title_locations) != 1:
                    continue

                title_row, title_column = map(int, title_locations[0])
                full_title = re.sub(
                    r"\s+", " ", raw_data.iat[title_row, title_column]
                ).strip()
                if ":" not in full_title:
                    continue
                city_name, current_report_title = (
                    part.strip() for part in full_title.split(":", 1)
                )
                if not city_name or not current_report_title:
                    continue

                header_row = None
                code_column = None
                label_column = None
                for row_index in range(title_row + 1, len(raw_data)):
                    row = raw_data.iloc[row_index]
                    division_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "division", exact=True
                        )
                    ]
                    description_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "descripcion", exact=True
                        )
                    ]
                    if division_columns and description_columns:
                        header_row = row_index
                        code_column = division_columns[0]
                        label_column = description_columns[0]
                        break
                if header_row is None or label_column <= code_column:
                    continue

                current_unit_title = ""
                for _, row in raw_data.iloc[
                    title_row + 1 : header_row
                ].iterrows():
                    parts = [
                        re.sub(r"\s+", " ", value).strip()
                        for value in row
                        if isinstance(value, str) and value.strip()
                    ]
                    if parts:
                        current_unit_title = " ".join(dict.fromkeys(parts))
                        break
                if not current_unit_title:
                    raise ValueError(
                        f"The unit title is missing for {city_name}."
                    )

                month_row = header_row + 1
                first_row = None
                for row_index in range(month_row + 1, len(raw_data)):
                    code = str(raw_data.iat[row_index, code_column]).strip()
                    label = raw_data.iat[row_index, label_column]
                    if (
                        re.fullmatch(r"0(?:\.0+)?", code)
                        and isinstance(label, str)
                        and search_key_words(
                            label.strip(), "indice general", exact=True
                        )
                    ):
                        first_row = row_index
                        break
                if first_row is None:
                    raise ValueError(
                        f"The INDICE GENERAL row is missing for {city_name}."
                    )

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
                        raise ValueError(
                            f"A division code is invalid for {city_name}."
                        )
                    if not isinstance(label, str) or not label.strip():
                        raise ValueError(
                            f"A division description is missing for {city_name}."
                        )
                    division_code = int(numeric_code)
                    if division_code in division_codes:
                        raise ValueError(
                            f"Duplicate division codes exist for {city_name}."
                        )
                    division_codes.add(division_code)
                    row_indices.append(row_index)
                if not row_indices or min(division_codes) != 0:
                    raise ValueError(
                        f"No valid division records exist for {city_name}."
                    )

                date_columns = {}
                current_year = None
                for column in range(label_column + 1, raw_data.shape[1]):
                    year_label = str(raw_data.iat[header_row, column]).strip()
                    year_match = re.search(
                        r"\b((?:19|20)\d{2})\b", year_label
                    )
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
                                "Unrecognized monthly header for "
                                f"{city_name}: {month_label}."
                            )
                        continue
                    if current_year is None:
                        raise ValueError(
                            f"A month has no year for {city_name}."
                        )
                    month_date = pd.Timestamp(current_year, month, 1)
                    date_columns[column] = (
                        month_date + pd.offsets.MonthEnd(0)
                    ).strftime(format)
                if not date_columns or len(set(date_columns.values())) != len(
                    date_columns
                ):
                    raise ValueError(
                        f"Monthly columns are invalid for {city_name}."
                    )

                labels = raw_data.loc[row_indices, label_column].map(
                    lambda value: re.sub(r"\s+", " ", value).strip()
                )
                current_divisions = tuple(labels)
                current_dates = tuple(date_columns.values())
                if reference_divisions is None:
                    reference_divisions = current_divisions
                    reference_dates = current_dates
                    report_title = current_report_title
                    unit_title = current_unit_title
                elif (
                    current_divisions != reference_divisions
                    or current_dates != reference_dates
                    or current_report_title != report_title
                    or current_unit_title != unit_title
                ):
                    raise ValueError(
                        f"The structure differs for {city_name}."
                    )
                if city_name in city_names:
                    raise ValueError(f"Duplicate city report: {city_name}.")
                city_names.add(city_name)

                table = raw_data.loc[
                    row_indices, list(date_columns)
                ].copy()
                table = table.rename(columns=date_columns)
                table.insert(0, "nv2", labels.to_list())
                table.insert(0, "nv1", city_name)
                city_frames.append(
                    table.melt(
                        id_vars=["nv1", "nv2"],
                        var_name="fecha",
                        value_name="valor",
                    )
                )

            if len(city_frames) != 9:
                raise ValueError(
                    "Exactly nine city reports are required; "
                    f"found {len(city_frames)}."
                )

            dataframe = pd.concat(city_frames, ignore_index=True)
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
            if dataframe.duplicated(["nv1", "nv2", "fecha"]).any():
                raise ValueError("Duplicate monthly division records exist.")

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": [report_title, unit_title],
                "page_number": int(page_number),
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
        """Return True when consolidated structure or values are invalid.

        Monthly percentage changes by division are not additive totals, so
        the general variation cannot be reconciled by summing divisions.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if decimal_separator not in {",", "."}:
                return True
            columns = ["nv1", "nv2", "fecha", "valor"]
            if not set(columns).issubset(dataframe.columns):
                return True
            data = dataframe[columns].copy()
            if not data[["nv1", "nv2", "fecha"]].map(
                lambda value: isinstance(value, str)
            ).all().all():
                return True
            if data[["nv1", "nv2"]].map(
                lambda value: not value.strip() or value.strip() == "-"
            ).any().any():
                return True
            if data.duplicated(["nv1", "nv2", "fecha"]).any():
                return True
            if data["nv1"].nunique() != 9:
                return True

            dates = pd.to_datetime(
                data["fecha"], format="%Y-%m-%d", errors="coerce"
            )
            if dates.isna().any() or not dates.dt.is_month_end.all():
                return True
            data["_date"] = dates
            unique_dates = pd.DatetimeIndex(sorted(dates.unique()))
            expected_dates = pd.date_range(
                unique_dates.min(), unique_dates.max(), freq="ME"
            )
            if not unique_dates.equals(expected_dates):
                return True

            city_divisions = data.groupby("nv1")["nv2"].agg(frozenset)
            city_dates = data.groupby("nv1")["_date"].agg(frozenset)
            if len(set(city_divisions)) != 1 or len(set(city_dates)) != 1:
                return True
            division_count = len(city_divisions.iloc[0])
            if division_count != 13:
                return True
            expected_rows = 9 * division_count * len(unique_dates)
            if len(data) != expected_rows:
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
            print(f"Could not validate consolidated IPC variation: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000016_01

Executor_D_BO_000000016_01 = D_BO_000000016_01
Robot = D_BO_000000016_01
