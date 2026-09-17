from models.conversion.Conversion_Base import Conversion_Base
"""Convert Bolivia's monthly cumulative IGAE variation report."""

import os
import re
import traceback
from datetime import date, datetime
from numbers import Real

import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import (
    get_xlsx_report_dataframe,
    search_key_words,
    to_numeric_datax,
)
from models.download.tools.download_tools import month_abr_to_number, month_to_number


class D_BO_000000045_01(Conversion_Base):
    """Extract cumulative rates by activity, subactivity and month."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "indice mes",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return document titles and all published monthly observations.

        Years come from the table headers, including merged year groups and
        year-month labels. Dates identify the last calendar day of each month.
        Hyphens in subactivity names are preserved; absent levels are empty.
        Rates retain the two decimals displayed by this report (factor 1).
        Return an empty string and print the traceback when extraction fails.
        """
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The initial sheet number must be positive.")

            search_terms = re.sub(
                r"\s+", " ", key_words or "indice mes"
            ).strip().lower()
            if search_terms == "indice mes":
                # The configured alias differs from the document title.
                search_terms = "variacion acumulada igae mes"
            report = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=search_terms,
                page_number=page_number,
            )
            if report is None:
                raise ValueError(
                    "The cumulative IGAE variation table was not found."
                )
            raw_data, found_page = report

            general_mask = raw_data.map(
                lambda value: isinstance(value, str)
                and search_key_words(value.strip(), "indice general", True)
            )
            locations = np.argwhere(general_mask.to_numpy())
            if len(locations) != 1:
                raise ValueError("A unique INDICE GENERAL row is required.")
            first_row, label_column = map(int, locations[0])
            month_row = first_row - 1
            year_row = month_row - 1
            if year_row < 1:
                raise ValueError("The report headers are incomplete.")

            titles = []
            for _, row in raw_data.iloc[:year_row].iterrows():
                parts = [
                    re.sub(r"\s+", " ", value).strip()
                    for value in row
                    if isinstance(value, str) and value.strip()
                ]
                title = " ".join(dict.fromkeys(parts))
                if title and title not in titles:
                    titles.append(title)
            if not titles:
                raise ValueError("The document titles were not found.")
            if not any(
                search_key_words(title, "variacion acumulada igae mes")
                for title in titles
            ):
                raise ValueError("The table is not cumulative IGAE variation.")

            date_columns = {}
            current_year = None
            for column in range(label_column + 1, raw_data.shape[1]):
                year_label = str(raw_data.iat[year_row, column]).strip()
                year_match = re.fullmatch(
                    r"((?:19|20)\d{2})(?:\.0|\s*\(p\))?",
                    year_label,
                    flags=re.IGNORECASE,
                )
                if year_match:
                    current_year = int(year_match.group(1))

                header = raw_data.iat[month_row, column]
                if isinstance(header, (date, datetime, pd.Timestamp)):
                    month_date = pd.Timestamp(header)
                    current_year = month_date.year
                else:
                    header = re.sub(
                        r"\(p\)", "", str(header), flags=re.IGNORECASE
                    ).strip()
                    explicit_year = re.search(r"\b((?:19|20)\d{2})\b", header)
                    if explicit_year:
                        current_year = int(explicit_year.group(1))
                        header = header.replace(explicit_year.group(0), "")
                    month_name = header.strip(" .-/_")
                    month = (
                        month_to_number(month_name)
                        or month_abr_to_number(month_name)
                    )
                    if month is None:
                        if raw_data.iloc[first_row:, column].notna().any():
                            raise ValueError(
                                f"Unrecognized monthly header: {header}."
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

            row_indices = []
            activities = []
            subactivities = []
            current_activity = None
            for row_index in range(first_row, len(raw_data)):
                label = raw_data.iat[row_index, label_column]
                if pd.isna(label) or not str(label).strip():
                    row_values = raw_data.loc[row_index, list(date_columns)]
                    if row_values.notna().any():
                        raise ValueError(
                            "An observation has no activity name."
                        )
                    continue
                label = re.sub(r"\s+", " ", str(label)).strip()
                if label.lower().startswith(("fuente", "nota", "(p)", "(1)")):
                    break
                if label.startswith("-"):
                    if current_activity is None:
                        raise ValueError(
                            "A subactivity has no parent activity."
                        )
                    subactivity = label
                else:
                    current_activity = label
                    subactivity = None
                row_indices.append(row_index)
                activities.append(current_activity)
                subactivities.append(subactivity)

            if not row_indices:
                raise ValueError("No monthly activity records were found.")
            table = raw_data.loc[row_indices, list(date_columns)].copy()
            table = table.rename(columns=date_columns)
            table.insert(0, "nv2", subactivities)
            table.insert(0, "nv1", activities)
            dataframe = table.melt(
                id_vars=["nv1", "nv2"],
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
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask & ~missing_mask
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], ","
            )
            if numeric.loc[~missing_mask].isna().any():
                raise ValueError("A rate contains invalid numeric text.")
            if not np.isfinite(numeric.dropna()).all() or numeric.isna().all():
                raise ValueError("The report has no valid finite rates.")
            dataframe["valor"] = numeric.round(2)
            if dataframe.duplicated(["nv1", "nv2", "fecha"]).any():
                raise ValueError("Duplicate monthly activity records exist.")

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
        """Return True for invalid structure, dates, hierarchy or numbers.

        Cumulative rates are not additive totals. Without published weights,
        summing sector rates cannot reconcile the general rate. Negative
        rates are valid; no division by 100 is applied to the source values.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if decimal_separator not in {",", "."}:
                return True
            columns = ["nv1", "nv2", "fecha", "valor"]
            if not set(columns).issubset(dataframe.columns):
                return True
            data = dataframe[columns]
            if not data[["nv1", "fecha"]].map(
                lambda value: isinstance(value, str) and value.strip() not in {"", "-"}
            ).all().all():
                return True
            if not data["nv2"].map(
                lambda value: value is None or pd.isna(value) or (isinstance(value, str) and value.strip() not in {"", "-"})
            ).all():
                return True
            if data.duplicated(["nv1", "nv2", "fecha"]).any():
                return True
            dates = pd.to_datetime(
                data["fecha"], format="%Y-%m-%d", errors="coerce"
            )
            if dates.isna().any() or not dates.dt.is_month_end.all():
                return True

            parent_rows = data.loc[data["nv2"].isna(), ["nv1", "fecha"]]
            child_rows = data.loc[data["nv2"].notna(), ["nv1", "fecha"]]
            parents = set(map(tuple, parent_rows.to_numpy()))
            children = set(map(tuple, child_rows.to_numpy()))
            if not children.issubset(parents):
                return True

            values = data["valor"]
            numeric_mask = values.map(
                lambda value: isinstance(value, Real)
                and not isinstance(value, (bool, np.bool_))
            )
            missing_mask = (
                values.isna() | values.astype(str).str.strip().eq("")
            )
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask & ~missing_mask
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], decimal_separator
            )
            return bool(
                numeric.loc[~missing_mask].isna().any()
                or numeric.isna().all()
                or not np.isfinite(numeric.dropna()).all()
            )
        except Exception as error:
            print(f"Could not validate the cumulative IGAE variation: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000045_01

Executor_D_BO_000000045_01 = D_BO_000000045_01
Robot = D_BO_000000045_01
