from models.conversion.Conversion_Base import Conversion_Base
import os
import traceback
from typing import Tuple, Union

import pandas as pd

from models.conversion.tools.conversion_tools import (
    extract_report_df,
    get_xlsx_report_dataframe,
    to_numeric_datax,
)


class D_BO_000000541_01(Conversion_Base):
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
        Extracts and normalizes CME Term SOFR rates data from an Excel file.

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
            # 1. Retrieve the sheet dataframe using existing conversion_tools
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

            # 2. Extract titles and split table starting from the header pivot
            splited_df, titles = extract_report_df(
                table_df,
                pivot_keywords="month",
                top_gap=1
            )

            # Dates are located in row 0, from column index 1 onwards
            date_headers = splited_df.iloc[0, 1:].tolist()

            # 3. Iterate through rate rows to extract normalized records
            records = []
            for idx in range(1, len(splited_df)):
                nv1 = str(splited_df.iloc[idx, 0]).strip()
                for c_idx, date_val in enumerate(date_headers):
                    if pd.isna(date_val):
                        continue

                    date_clean = str(date_val).strip()
                    fecha_str = pd.to_datetime(date_clean).strftime(format)
                    val = splited_df.iloc[idx, c_idx + 1]
                    val_clean = float(str(val).strip())

                    records.append({
                        "nv1": nv1,
                        "fecha": fecha_str,
                        "valor": val_clean
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
        Validates consistency between printed totals and component sums.

        Args:
            dataframe: Normalized DataFrame (with or without metadata columns).
            decimal_separator: Decimal separator configured ('.' or ',').
            TOLERANCE: Allowed tolerance for rounding differences.

        Returns:
            False if all printed totals match calculated sums or no totals.
            True if any discrepancy exceeds TOLERANCE.
        """
        numeric_series = to_numeric_datax(dataframe["valor"],
                                          decimal_separator)
        temp_df = dataframe.copy()
        temp_df["_numeric_valor"] = numeric_series

        # Find the categorical column containing 'TOTAL'
        exclude_cols = {"valor", "_numeric_valor", "fecha", "file"}
        cat_cols = [
            col for col in temp_df.columns
            if col not in exclude_cols and not str(col).startswith("titulo")
        ]

        total_col = None
        for col in cat_cols:
            is_total_mask = (
                temp_df[col].astype(str).str.strip().str.upper() == "TOTAL"
            )
            if is_total_mask.any():
                total_col = col
                break

        # If no total column exists, there are no printed totals to validate
        if not total_col:
            return False

        # Group by date to compare printed totals against calculated sums
        total_mask = (
            temp_df[total_col].astype(str).str.strip().str.upper() == "TOTAL"
        )
        totals = temp_df[total_mask].groupby("fecha")["_numeric_valor"].sum()
        components = (
            temp_df[~total_mask].groupby("fecha")["_numeric_valor"].sum()
        )

        comparison = pd.concat(
            [totals.rename("total_printed"), components.rename("total_calc")],
            axis=1
        ).dropna()

        discrepancies = (
            comparison["total_printed"] - comparison["total_calc"]
        ).abs()

        has_error = (discrepancies > TOLERANCE).any()
        if has_error:
            failed = comparison[discrepancies > TOLERANCE]
            print(f"Validation failed for dates:\n{failed}")

        return bool(has_error)

Executor_D_BO_000000541_01 = D_BO_000000541_01
Robot = D_BO_000000541_01
