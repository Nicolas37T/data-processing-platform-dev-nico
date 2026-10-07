from models.conversion.Conversion_Base import Conversion_Base
"""Convert registered heating power reported by electricity agents."""

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


class D_BO_000000067_01(Conversion_Base):
    """Extract monthly registered heating power by reporting agent."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "poder calorifico",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return report metadata and normalized monthly observations."""
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The page number must be positive.")

            search_terms = re.sub(
                r"\s+", " ", key_words or "poder calorifico"
            ).strip().lower()
            if search_terms == "poder calorifico":
                search_terms = (
                    "poder calorifico registrado informado agentes"
                )

            report = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=search_terms,
                page_number=page_number,
            )
            if report is None:
                raise ValueError(
                    "The registered heating power table was not found."
                )
            raw_data, found_page = report

            title_mask = raw_data.map(
                lambda value: isinstance(value, str)
                and search_key_words(value, search_terms)
            )
            title_locations = np.argwhere(title_mask.to_numpy())
            if len(title_locations) != 1:
                raise ValueError(
                    "A unique registered heating power title is required."
                )
            title_row = int(title_locations[0][0])

            header_row = None
            agent_columns = {}
            for row_index in range(title_row + 1, len(raw_data)):
                row = raw_data.iloc[row_index]
                candidates = {
                    int(column): re.sub(r"\s+", " ", value).strip()
                    for column, value in row.items()
                    if int(column) > 0
                    and isinstance(value, str)
                    and value.strip()
                }
                first_value = row.iloc[0]
                if pd.isna(first_value) and len(candidates) >= 2:
                    header_row = row_index
                    agent_columns = candidates
                    break
            if header_row is None or not agent_columns:
                raise ValueError("The reporting agent headers were not found.")
            if len(set(agent_columns.values())) != len(agent_columns):
                raise ValueError("Duplicate reporting agent headers exist.")

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

            year_candidates = []
            for title in titles:
                if search_key_words(title, "ano"):
                    year_candidates.extend(
                        int(year)
                        for year in re.findall(r"\b((?:19|20)\d{2})\b", title)
                    )
            report_years = set(year_candidates)
            if len(report_years) != 1:
                raise ValueError("A unique report year is required.")
            report_year = report_years.pop()

            records = []
            monthly_rows_found = False
            for row_index in range(header_row + 1, len(raw_data)):
                month_value = raw_data.iat[row_index, 0]
                month_label = re.sub(
                    r"\s+", " ", str(month_value)
                ).strip(" .-/_")
                month = (
                    month_to_number(month_label)
                    or month_abr_to_number(month_label)
                )
                if month is None:
                    if monthly_rows_found:
                        break
                    continue
                monthly_rows_found = True

                row_values = raw_data.loc[
                    row_index, list(agent_columns)
                ]
                if row_values.isna().all():
                    continue
                if row_values.isna().any():
                    raise ValueError(
                        f"Incomplete agent values exist for {month_label}."
                    )

                last_day = calendar.monthrange(report_year, month)[1]
                report_date = pd.Timestamp(
                    report_year, month, last_day
                ).strftime(format)
                for column, agent_name in agent_columns.items():
                    records.append(
                        {
                            "nv1": agent_name,
                            "fecha": report_date,
                            "valor": raw_data.iat[row_index, column],
                        }
                    )

            dataframe = pd.DataFrame(
                records, columns=["nv1", "fecha", "valor"]
            )
            if dataframe.empty:
                raise ValueError("No monthly observations were extracted.")

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
                raise ValueError("A heating power value is not numeric.")
            dataframe["valor"] = numeric.round(2)

            if dataframe.duplicated(["nv1", "fecha"]).any():
                raise ValueError("Duplicate agent and month records exist.")

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

        This report contains independent measurements and has no printed
        totals to reconcile arithmetically.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if decimal_separator not in {",", "."}:
                return True
            columns = ["nv1", "fecha", "valor"]
            if not set(columns).issubset(dataframe.columns):
                return True

            data = dataframe[columns].copy()
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
            if dates.dt.year.nunique() != 1:
                return True

            unique_dates = pd.DatetimeIndex(sorted(dates.unique()))
            expected_dates = pd.date_range(
                start=pd.Timestamp(unique_dates.min().year, 1, 31),
                end=unique_dates.max(),
                freq="ME",
            )
            if not unique_dates.equals(expected_dates):
                return True

            agent_sets = data.groupby("fecha")["nv1"].agg(frozenset)
            date_sets = data.assign(_date=dates).groupby("nv1")[
                "_date"
            ].agg(frozenset)
            if len(set(agent_sets)) != 1 or len(set(date_sets)) != 1:
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
            print(f"Could not validate heating power data: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000067_01 = D_BO_000000067_01
Robot = D_BO_000000067_01
