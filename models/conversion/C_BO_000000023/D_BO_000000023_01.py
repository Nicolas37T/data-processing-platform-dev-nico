from models.conversion.Conversion_Base import Conversion_Base
"""Convert Bolivia's basic-services consumption index report."""

import calendar
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

class D_BO_000000023_01(Conversion_Base):
    """Extract annual and monthly indices by basic service."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "servicios basicos",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return report metadata and normalized index observations.

        Indicator names, period labels and years come from the worksheet.
        Monthly dates use the last calendar day, while annual observations
        use December 31. Published indices retain two decimal places.
        """
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The initial sheet number must be positive.")

            search_terms = re.sub(
                r"\s+", " ", key_words or "servicios basicos"
            ).strip().lower()
            report = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=search_terms,
                page_number=page_number,
            )
            if report is None:
                raise ValueError(
                    "The basic-services consumption index was not found."
                )
            raw_data, found_page = report

            title_mask = raw_data.map(
                lambda value: isinstance(value, str)
                and search_key_words(value, search_terms)
            )
            title_locations = np.argwhere(title_mask.to_numpy())
            if len(title_locations) != 1:
                raise ValueError(
                    "A unique basic-services report title is required."
                )
            title_row, label_column = map(int, title_locations[0])

            header_row = None
            indicator_columns = {}
            for row_index in range(title_row + 1, len(raw_data)):
                label = raw_data.iat[row_index, label_column]
                if not (
                    isinstance(label, str)
                    and search_key_words(label.strip(), "periodo", True)
                ):
                    continue
                candidates = {
                    int(column): re.sub(r"\s+", " ", value).strip()
                    for column, value in raw_data.iloc[row_index].items()
                    if int(column) > label_column
                    and isinstance(value, str)
                    and value.strip()
                }
                if len(candidates) >= 2:
                    header_row = row_index
                    indicator_columns = candidates
                    break
            if header_row is None or not indicator_columns:
                raise ValueError("The indicator headers were not found.")
            if len(set(indicator_columns.values())) != len(
                indicator_columns
            ):
                raise ValueError("Duplicate indicator headers exist.")

            titles = []
            for _, row in raw_data.iloc[title_row:header_row].iterrows():
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

            records = []
            current_year = None
            observations_found = False
            year_pattern = re.compile(
                r"^((?:19|20)\d{2})(?:\s*\(p\))?$",
                flags=re.IGNORECASE,
            )
            for row_index in range(header_row + 1, len(raw_data)):
                raw_label = raw_data.iat[row_index, label_column]
                row_values = raw_data.loc[
                    row_index, list(indicator_columns)
                ]
                if pd.isna(raw_label) or not str(raw_label).strip():
                    if row_values.notna().any():
                        raise ValueError(
                            "An observation has no period label."
                        )
                    continue

                period_label = re.sub(
                    r"\s+", " ", str(raw_label)
                ).strip()
                if period_label.lower().startswith(
                    ("fuente", "nota", "(p)")
                ):
                    if observations_found:
                        break
                    continue

                year_match = year_pattern.fullmatch(period_label)
                if year_match:
                    current_year = int(year_match.group(1))
                    period_month = 12
                else:
                    period_month = (
                        month_to_number(period_label)
                        or month_abr_to_number(period_label)
                    )
                    if period_month is None:
                        if row_values.notna().any():
                            raise ValueError(
                                f"Unrecognized period label: {period_label}."
                            )
                        continue
                    if current_year is None:
                        raise ValueError(
                            "A monthly row has no associated year."
                        )

                if row_values.isna().all():
                    continue
                if row_values.isna().any():
                    raise ValueError(
                        f"Incomplete values exist for {period_label}."
                    )
                observations_found = True

                last_day = calendar.monthrange(
                    current_year, period_month
                )[1]
                report_date = pd.Timestamp(
                    current_year, period_month, last_day
                ).strftime(format)
                for column, indicator_name in indicator_columns.items():
                    records.append(
                        {
                            "nv1": indicator_name,
                            "nv2": period_label,
                            "fecha": report_date,
                            "valor": raw_data.iat[row_index, column],
                        }
                    )

            dataframe = pd.DataFrame(
                records, columns=["nv1", "nv2", "fecha", "valor"]
            )
            if dataframe.empty:
                raise ValueError("No index observations were extracted.")

            values = dataframe["valor"]
            numeric_mask = values.map(
                lambda value: isinstance(value, Real)
                and not isinstance(value, (bool, np.bool_))
            )
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask & values.notna()
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], ","
            )
            if numeric.isna().any() or not np.isfinite(numeric).all():
                raise ValueError("An index value is not numeric and finite.")
            dataframe["valor"] = numeric.round(2)

            if dataframe.duplicated(
                ["nv1", "nv2", "fecha"]
            ).any():
                raise ValueError("Duplicate indicator-period records exist.")

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
        """Return True when structure, periods or values are invalid.

        These indices are independent weighted measures, so the GENERAL
        series cannot be reconciled by summing the service indices.
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

            dates = pd.to_datetime(
                data["fecha"], format="%Y-%m-%d", errors="coerce"
            )
            if dates.isna().any() or not dates.dt.is_month_end.all():
                return True

            annual_years = data["nv2"].str.extract(
                r"^((?:19|20)\d{2})(?:\s*\(p\))?$",
                flags=re.IGNORECASE,
                expand=False,
            )
            annual_mask = annual_years.notna()
            if not annual_mask.any() or annual_mask.all():
                return True
            annual_dates = dates.loc[annual_mask]
            if not (
                annual_dates.dt.year.to_numpy()
                == annual_years.loc[annual_mask].astype(int).to_numpy()
            ).all():
                return True
            if not annual_dates.dt.month.eq(12).all():
                return True

            monthly_periods = data.loc[~annual_mask, "nv2"]
            monthly_numbers = monthly_periods.map(
                lambda label: month_to_number(label)
                or month_abr_to_number(label)
            )
            if monthly_numbers.isna().any():
                return True
            if not (
                dates.loc[~annual_mask].dt.month.to_numpy()
                == monthly_numbers.astype(int).to_numpy()
            ).all():
                return True

            indicator_sets = data.groupby(["nv2", "fecha"])["nv1"].agg(
                frozenset
            )
            if len(set(indicator_sets)) != 1:
                return True
            period_sets = data.assign(
                _period=data["nv2"] + "|" + data["fecha"]
            ).groupby("nv1")["_period"].agg(frozenset)
            if len(set(period_sets)) != 1:
                return True

            monthly_dates = pd.DatetimeIndex(
                sorted(dates.loc[~annual_mask].unique())
            )
            expected_dates = pd.date_range(
                start=monthly_dates.min(),
                end=monthly_dates.max(),
                freq="ME",
            )
            if not monthly_dates.equals(expected_dates):
                return True
            if set(annual_years.dropna().astype(int)) != set(
                monthly_dates.year
            ):
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
            print(f"Could not validate basic-services indices: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000023_01 = D_BO_000000023_01
Robot = D_BO_000000023_01
