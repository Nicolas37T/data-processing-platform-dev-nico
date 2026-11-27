from models.conversion.Conversion_Base import Conversion_Base
"""Convert monthly average prices by city and product."""

import os
import re
import traceback
from decimal import Decimal
from numbers import Real

import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import search_key_words, to_numeric_datax
from models.download.tools.download_tools import month_abr_to_number, month_to_number

class D_BO_000000015_01(Conversion_Base):
    """Extract monthly average prices from every reported city sheet."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "precios promedio",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """Return one consolidated DataFrame for all nine city reports.

        Report sheets, product dimensions, years and months are detected
        from workbook content. Blank source observations are omitted without
        creating values, and the conversion factor is 1.
        """
        try:
            if os.path.splitext(file_path)[1].lower() not in {".xls", ".xlsx"}:
                raise ValueError("The source must be an XLS or XLSX workbook.")
            if not isinstance(page_number, int) or page_number < 1:
                raise ValueError("The page number must be positive.")

            def clean_text(value: object) -> str:
                """Normalize cell text without changing its meaning."""
                if pd.isna(value):
                    return ""
                return re.sub(r"\s+", " ", str(value)).strip()

            def parse_product_code(value: object, city_name: str) -> str:
                """Return a product identifier without numeric artifacts."""
                code_text = clean_text(value)
                if isinstance(value, Real) and not isinstance(
                    value, (bool, np.bool_)
                ):
                    if not float(value).is_integer():
                        raise ValueError(
                            f"A product code is invalid for {city_name}."
                        )
                    return str(int(value))
                product_code = re.sub(r"\s+", "", code_text)
                if not re.fullmatch(r"[0-9A-Za-z]+", product_code):
                    raise ValueError(
                        f"Invalid product code for {city_name}: {code_text}."
                    )
                return product_code

            def parse_quantity(
                value: object,
                product_code: str,
                city_name: str,
            ) -> str:
                """Return a positive quantity with at least two decimals."""
                if isinstance(value, Real) and not isinstance(
                    value, (bool, np.bool_)
                ):
                    quantity_number = float(value)
                else:
                    quantity_number = to_numeric_datax(
                        pd.Series([value]), ","
                    ).iloc[0]
                if (
                    pd.isna(quantity_number)
                    or not np.isfinite(quantity_number)
                    or quantity_number <= 0
                ):
                    raise ValueError(
                        "Invalid quantity for product "
                        f"{product_code} in {city_name}."
                    )

                quantity = (
                    f"{Decimal(str(quantity_number)).normalize():f}"
                )
                if "." not in quantity:
                    return f"{quantity}.00"
                integer, decimals = quantity.split(".", 1)
                return f"{integer}.{decimals.ljust(2, '0')}"

            def extract_sheet(
                sheet_name: str,
                raw_data: pd.DataFrame,
            ) -> dict | None:
                """Extract one report sheet using structural pivots."""
                title_mask = raw_data.map(
                    lambda value: isinstance(value, str)
                    and search_key_words(value, search_terms)
                )
                title_locations = np.argwhere(title_mask.to_numpy())
                if not len(title_locations):
                    return None
                if len(title_locations) != 1:
                    raise ValueError(
                        f"A unique report title is required for {sheet_name}."
                    )

                title_row, title_column = map(int, title_locations[0])
                full_title = clean_text(
                    raw_data.iat[title_row, title_column]
                )
                if ":" not in full_title:
                    raise ValueError(
                        f"The city is missing from the title for {sheet_name}."
                    )
                city_title, report_title = (
                    part.strip() for part in full_title.split(":", 1)
                )
                city_name = clean_text(sheet_name)
                if not city_title or not report_title or not city_name:
                    raise ValueError(
                        f"The report title is invalid for {sheet_name}."
                    )

                header_row = None
                code_column = None
                label_column = None
                quantity_column = None
                unit_column = None
                for row_index in range(title_row + 1, len(raw_data)):
                    row = raw_data.iloc[row_index]
                    code_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "variedad", exact=True
                        )
                    ]
                    label_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "descripcion", exact=True
                        )
                    ]
                    quantity_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "cantidad", exact=True
                        )
                    ]
                    unit_columns = [
                        int(column)
                        for column, value in row.items()
                        if isinstance(value, str)
                        and search_key_words(
                            value.strip(), "unidad medida", exact=True
                        )
                    ]
                    if (
                        code_columns
                        and label_columns
                        and quantity_columns
                        and unit_columns
                    ):
                        header_row = row_index
                        code_column = code_columns[0]
                        label_column = label_columns[0]
                        quantity_column = quantity_columns[0]
                        unit_column = unit_columns[0]
                        break

                columns = [
                    code_column,
                    label_column,
                    quantity_column,
                    unit_column,
                ]
                if (
                    header_row is None
                    or any(column is None for column in columns)
                    or columns != sorted(columns)
                    or len(set(columns)) != len(columns)
                ):
                    raise ValueError(
                        f"Product headers are missing for {city_name}."
                    )

                unit_title = ""
                for _, row in raw_data.iloc[
                    title_row + 1 : header_row
                ].iterrows():
                    parts = [
                        clean_text(value)
                        for value in row
                        if isinstance(value, str) and value.strip()
                    ]
                    if parts:
                        unit_title = " ".join(dict.fromkeys(parts))
                        break
                if not unit_title:
                    raise ValueError(
                        f"The unit title is missing for {city_name}."
                    )

                month_row = header_row + 1
                row_indices = []
                categories = []
                product_codes = []
                descriptions = []
                quantities = []
                units = []
                current_category = ""

                for row_index in range(month_row + 1, len(raw_data)):
                    raw_code = raw_data.iat[row_index, code_column]
                    raw_label = raw_data.iat[row_index, label_column]
                    code_text = clean_text(raw_code)
                    label_text = clean_text(raw_label)
                    footer_text = f"{code_text} {label_text}".strip()
                    if search_key_words(footer_text, "fuente"):
                        break
                    if not code_text and not label_text:
                        continue

                    row_values = raw_data.iloc[
                        row_index, unit_column + 1 :
                    ]
                    if not code_text:
                        if row_values.notna().any():
                            raise ValueError(
                                "A category row contains monthly values for "
                                f"{city_name}."
                            )
                        current_category = label_text
                        continue
                    if not current_category:
                        raise ValueError(
                            "A product appears before its category for "
                            f"{city_name}."
                        )
                    if not label_text:
                        raise ValueError(
                            f"A product has no description for {city_name}."
                        )

                    product_code = parse_product_code(
                        raw_code, city_name
                    )
                    quantity = parse_quantity(
                        raw_data.iat[row_index, quantity_column],
                        product_code,
                        city_name,
                    )
                    unit = clean_text(
                        raw_data.iat[row_index, unit_column]
                    )
                    if not unit or unit == "-":
                        raise ValueError(
                            "A product has no unit for "
                            f"{city_name}: {product_code}."
                        )

                    row_indices.append(row_index)
                    categories.append(current_category)
                    product_codes.append(product_code)
                    descriptions.append(label_text)
                    quantities.append(quantity)
                    units.append(unit)

                if not row_indices:
                    raise ValueError(
                        f"No valid product rows exist for {city_name}."
                    )
                product_keys = pd.DataFrame(
                    {
                        "nv2": categories,
                        "nv3": product_codes,
                        "nv4": descriptions,
                        "nv5": quantities,
                        "nv6": units,
                    }
                )
                if product_keys.duplicated().any():
                    raise ValueError(
                        f"Duplicate product presentations exist for "
                        f"{city_name}."
                    )

                date_columns = {}
                current_year = None
                for column in range(
                    unit_column + 1, raw_data.shape[1]
                ):
                    year_label = clean_text(
                        raw_data.iat[header_row, column]
                    )
                    year_match = re.search(
                        r"\b((?:19|20)\d{2})\b", year_label
                    )
                    if year_match:
                        current_year = int(year_match.group(1))

                    month_label = raw_data.iat[month_row, column]
                    month_name = clean_text(month_label).strip(" .-/_")
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

                table = raw_data.loc[
                    row_indices, list(date_columns)
                ].copy()
                table = table.rename(columns=date_columns)
                table.insert(0, "_row_order", range(len(table)))
                table.insert(0, "nv6", units)
                table.insert(0, "nv5", quantities)
                table.insert(0, "nv4", descriptions)
                table.insert(0, "nv3", product_codes)
                table.insert(0, "nv2", categories)
                table.insert(0, "nv1", city_name)
                dataframe = table.melt(
                    id_vars=[
                        "nv1",
                        "nv2",
                        "nv3",
                        "nv4",
                        "nv5",
                        "nv6",
                        "_row_order",
                    ],
                    var_name="fecha",
                    value_name="valor",
                )
                dataframe = dataframe.sort_values(
                    ["_row_order", "fecha"]
                ).drop(columns="_row_order")

                return {
                    "city_name": city_name,
                    "full_title": full_title,
                    "report_title": report_title,
                    "unit_title": unit_title,
                    "dates": tuple(date_columns.values()),
                    "dataframe": dataframe,
                }

            search_terms = re.sub(
                r"\s+", " ", key_words or "precios promedio"
            ).strip().lower()
            sheets = pd.read_excel(
                file_path, sheet_name=None, header=None
            )
            city_frames = []
            city_names = set()
            city_titles = {}
            reference_dates = None
            report_title = None
            unit_title = None

            for sheet_name, raw_data in sheets.items():
                result = extract_sheet(sheet_name, raw_data)
                if result is None:
                    continue
                city_name = result["city_name"]
                if city_name in city_names:
                    raise ValueError(f"Duplicate city report: {city_name}.")
                city_names.add(city_name)
                city_titles[city_name] = result["full_title"]

                if reference_dates is None:
                    reference_dates = result["dates"]
                    report_title = result["report_title"]
                    unit_title = result["unit_title"]
                elif (
                    result["dates"] != reference_dates
                    or result["report_title"] != report_title
                    or result["unit_title"] != unit_title
                ):
                    raise ValueError(
                        f"The monthly structure differs for {city_name}."
                    )
                city_frames.append(result["dataframe"])

            if len(city_frames) != 9:
                raise ValueError(
                    "Exactly nine city reports are required; "
                    f"found {len(city_frames)}."
                )

            dataframe = pd.concat(city_frames, ignore_index=True)
            values = dataframe["valor"].map(
                lambda value: re.sub(r"^\s*\*\s*", "", value)
                if isinstance(value, str)
                else value
            )
            dataframe["valor"] = values
            missing_mask = values.isna() | values.astype(str).str.strip().isin(
                ["", "-", "..", "..."]
            )
            dataframe = dataframe.loc[~missing_mask].copy()
            values = dataframe["valor"]
            numeric_mask = values.map(
                lambda value: isinstance(value, Real)
                and not isinstance(value, (bool, np.bool_))
            )
            numeric = pd.to_numeric(
                values.where(numeric_mask), errors="coerce"
            )
            text_mask = ~numeric_mask
            numeric.loc[text_mask] = to_numeric_datax(
                values.loc[text_mask], ","
            )
            if numeric.isna().any() or not np.isfinite(numeric).all():
                raise ValueError("A price is not finite numeric data.")
            dataframe["valor"] = numeric.round(2)
            dataframe = dataframe.reset_index(drop=True)

            record_key = [
                "nv1",
                "nv2",
                "nv3",
                "nv4",
                "nv5",
                "nv6",
                "fecha",
            ]
            if dataframe.duplicated(record_key).any():
                raise ValueError("Duplicate product-month records exist.")

            title_series = dataframe["nv1"].map(city_titles)
            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": [title_series, unit_title],
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

        Product prices describe independent presentations and are not
        additive, so no arithmetic total should be reconciled.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if decimal_separator not in {",", "."}:
                return True
            levels = [f"nv{level}" for level in range(1, 7)]
            columns = levels + ["fecha", "valor"]
            if not set(columns).issubset(dataframe.columns):
                return True

            data = dataframe[columns].copy()
            if not data[levels + ["fecha"]].map(
                lambda value: isinstance(value, str)
            ).all().all():
                return True
            if data[levels + ["fecha"]].map(
                lambda value: not value.strip() or value.strip() == "-"
            ).any().any():
                return True
            if data["nv1"].nunique() != 9:
                return True

            record_key = levels + ["fecha"]
            if data.duplicated(record_key).any():
                return True
            if not data["nv3"].str.fullmatch(r"[0-9A-Za-z]+").all():
                return True
            if not data["nv5"].str.fullmatch(
                r"\d+(?:\.\d+)?"
            ).all():
                return True
            quantities = pd.to_numeric(data["nv5"], errors="coerce")
            if (
                quantities.isna().any()
                or not np.isfinite(quantities).all()
                or quantities.le(0).any()
            ):
                return True
            if data.groupby(
                ["nv1", "nv3", "nv4", "nv5", "nv6"]
            )["nv2"].nunique().gt(1).any():
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

            city_dates = data.groupby("nv1")["_date"].agg(frozenset)
            if len(city_dates) != 9 or len(set(city_dates)) != 1:
                return True
            series_dates = data.groupby(levels)["_date"].agg(frozenset)
            if series_dates.empty:
                return True
            series_counts = series_dates.map(len)
            if series_counts.min() < len(unique_dates) - 1:
                return True
            date_counts = data.groupby("_date").size()
            if date_counts.max() - date_counts.min() > 1:
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
            print(f"Could not validate average product prices: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000015_01 = D_BO_000000015_01
Robot = D_BO_000000015_01
