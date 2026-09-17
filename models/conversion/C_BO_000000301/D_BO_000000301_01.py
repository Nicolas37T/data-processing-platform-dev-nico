from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
from typing import Tuple, Union

import pandas as pd

from models.conversion.tools.conversion_tools import (
    get_xlsx_report_dataframe,
    last_day_month,
    month_abr_to_number,
    to_numeric_datax,
)


class D_BO_000000301_01(Conversion_Base):
    """Robot class for data extraction and validation."""

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> Union[Tuple[dict, pd.DataFrame], str]:
        """
        Extracts and normalizes ASFI ranking data.

        Args:
            file_path: Absolute or relative path to the downloaded Excel file.
            key_words: Keywords used to identify and validate the table.
            template_path: Path to the reference template (if applicable).
            page_number: Target sheet index (1-based).
            format: Expected output date format string.

        Returns:
            A tuple containing (metadata_dict, normalized_dataframe),
            or an empty string "" in case of an unrecoverable error.
        """
        try:
            # Handle potential .xls vs .xlsx extension discrepancy
            if not os.path.exists(file_path):
                if file_path.endswith(".xlsx") and os.path.exists(
                    file_path[:-1]
                ):
                    file_path = file_path[:-1]
                elif file_path.endswith(".xls") and os.path.exists(
                    file_path + "x"
                ):
                    file_path = file_path + "x"

            # 1. Retrieve the sheet dataframe using conversion_tools
            result = get_xlsx_report_dataframe(
                file_path=file_path,
                key_words=key_words,
                page_number=page_number
            )
            if result is None:
                raise ValueError(
                    f"Could not find table matching keywords in {file_path}"
                )

            table_df, detected_page = result

            # 2. Dynamically locate the header row containing month dates
            date_pattern = re.compile(
                r"\b(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)-\d{2}\b",
                re.IGNORECASE
            )

            date_row_idx = None
            for idx in range(len(table_df)):
                row_vals = [
                    str(x) for x in table_df.iloc[idx].values if pd.notna(x)
                ]
                if any(date_pattern.search(v) for v in row_vals):
                    date_row_idx = idx
                    break

            if date_row_idx is None:
                raise ValueError(
                    f"Could not locate date header row in {file_path}"
                )

            # Extract report titles from rows preceding the date header
            titles = []
            for idx in range(date_row_idx):
                line = " ".join(
                    str(x).strip()
                    for x in table_df.iloc[idx].dropna()
                    if str(x).strip()
                )
                if line:
                    clean_title = re.sub(
                        r"INTERMEDIACI.N", "INTERMEDIACIÓN", line
                    )
                    titles.append(clean_title)

            # Dates are in date_row_idx (forward filled across merged columns)
            dates_series = table_df.iloc[date_row_idx].ffill()
            # Metrics are in the row immediately below the date header
            metrics_series = table_df.iloc[date_row_idx + 1]

            # Identify data columns that have metric names
            data_cols = [
                c for c in range(len(table_df.columns))
                if pd.notna(metrics_series.iloc[c])
                and str(metrics_series.iloc[c]).strip()
            ]
            if not data_cols:
                raise ValueError("No data columns identified in table")

            entity_col = data_cols[0] - 1

            records = []
            current_nv1 = None

            # 3. Iterate through data rows following the metric header row
            for idx in range(date_row_idx + 2, len(table_df)):
                cell_entity = table_df.iloc[idx, entity_col]
                if pd.isna(cell_entity):
                    continue

                entity_str = str(cell_entity).strip()
                # Skip footnotes or empty rows
                if not entity_str or entity_str.startswith("("):
                    continue

                # Check if row has any non-null data values
                has_data = any(
                    pd.notna(table_df.iloc[idx, c]) for c in data_cols
                )

                # Section header row
                if not has_data:
                    clean_sec = re.sub(r"\s*\(\d+\)", "", entity_str).strip()
                    clean_sec = re.sub(r"M.LTIPLES", "MÚLTIPLES", clean_sec)
                    clean_sec = re.sub(r"CR.DITO", "CRÉDITO", clean_sec)
                    current_nv1 = clean_sec
                    continue

                # Data row: TOTAL, SUB-TOTAL, or entity code
                if entity_str == "TOTAL":
                    nv1 = "TOTAL"
                    nv2 = "TOTAL"
                elif entity_str == "SUB-TOTAL":
                    nv1 = current_nv1
                    nv2 = "SUB-TOTAL"
                else:
                    nv1 = current_nv1
                    nv2 = re.sub(r"\s*\(\d+\)", "", entity_str).strip()

                # Process each metric column
                for c in data_cols:
                    date_raw = str(dates_series.iloc[c]).strip()
                    metric = str(metrics_series.iloc[c]).strip()

                    # Convert date (e.g. DIC-20 -> 2020-12-31)
                    parts = date_raw.split("-")
                    m_num = month_abr_to_number(parts[0])
                    if len(parts[1]) == 2:
                        y_val = 2000 + int(parts[1])
                    else:
                        y_val = int(parts[1])
                    d_val = last_day_month(year=y_val, month=m_num)
                    fecha_str = f"{y_val}-{m_num:02d}-{d_val:02d}"

                    raw_val = table_df.iloc[idx, c]
                    if pd.isna(raw_val) or str(raw_val).strip() in [
                        "- - -", "-", "nan", ""
                    ]:
                        val_str = "-"
                    else:
                        num = float(raw_val)
                        if "%" in metric:
                            val_str = f"{round(num * 100, 2):.2f}"
                        elif "RANKING" in metric.upper():
                            val_str = str(int(round(num)))
                        else:
                            val_str = f"{round(num):,}"

                    records.append({
                        "nv1": nv1,
                        "nv2": nv2,
                        "nv3": metric,
                        "fecha": fecha_str,
                        "valor": val_str
                    })

            report_df = pd.DataFrame(records)

            file_name = os.path.basename(file_path)
            report_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": detected_page
            }

            return report_dict, report_df

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str,
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates arithmetic consistency between subtotals and printed totals.

        Args:
            dataframe: Normalized DataFrame (with or without metadata columns).
            decimal_separator: Decimal separator configured ('.' or ',').
            TOLERANCE: Allowed tolerance for rounding differences.

        Returns:
            False if all totals match calculated sums or no totals exist.
            True if any discrepancy exceeds TOLERANCE.
        """
        cleaned_valor = (
            dataframe["valor"].astype(str).str.replace(",", "", regex=False)
        )
        numeric_series = to_numeric_datax(cleaned_valor, ".")
        temp_df = dataframe.copy()
        temp_df["_numeric_valor"] = numeric_series

        # Validate monetary subtotals against grand TOTAL
        is_amount = (
            (~temp_df["nv3"].str.contains("%", na=False))
            & (~temp_df["nv3"].str.upper().str.contains("RANKING", na=False))
            if "nv3" in temp_df.columns
            else pd.Series(True, index=temp_df.index)
        )
        amt_df = temp_df[is_amount]

        subtotal_mask = (
            amt_df["nv2"].astype(str).str.strip().str.upper() == "SUB-TOTAL"
            if "nv2" in amt_df.columns
            else pd.Series(False, index=amt_df.index)
        )
        total_mask = (
            amt_df["nv2"].astype(str).str.strip().str.upper() == "TOTAL"
            if "nv2" in amt_df.columns
            else pd.Series(False, index=amt_df.index)
        )

        if subtotal_mask.any() and total_mask.any():
            subtotals = (
                amt_df[subtotal_mask].groupby("fecha")["_numeric_valor"]
                .sum()
            )
            totals = (
                amt_df[total_mask].groupby("fecha")["_numeric_valor"]
                .sum()
            )
            discrepancies = (subtotals - totals).abs()
            if (discrepancies > TOLERANCE).any():
                failed = discrepancies[discrepancies > TOLERANCE]
                print(f"Validation failed for totals:\n{failed}")
                return True

        return False

Executor_D_BO_000000301_01 = D_BO_000000301_01
Robot = D_BO_000000301_01
