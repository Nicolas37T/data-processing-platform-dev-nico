from models.conversion.Conversion_Base import Conversion_Base
import datetime
import os
import re
import traceback
from typing import Tuple, Union

import pandas as pd

from models.conversion.tools.conversion_tools import (
    extract_report_df,
    get_xlsx_report_dataframe,
    to_numeric_datax,
)
from models.download.tools.download_tools import last_day_month, month_to_number


class D_BO_000000019_01(Conversion_Base):

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> Union[Tuple[dict, pd.DataFrame], str]:
       
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
                pivot_keywords="periodo"
            )

            # Department columns are in row 0, from index 1 to the end
            header_row = splited_df.iloc[0]
            dept_cols = [str(col).strip() for col in header_row.iloc[1:]]

            # 3. Iterate through rows to extract monthly records
            records = []
            current_year = None

            for idx in range(1, len(splited_df)):
                cell_val = splited_df.iloc[idx, 0]
                if pd.isna(cell_val):
                    continue

                cell_str = str(cell_val).strip()

                if "fuente" in cell_str.lower():
                    break

                month_num = month_to_number(cell_str.lower())
                year_match = re.search(r"(\d{4})", cell_str)

                if month_num is None and year_match:
                    current_year = int(year_match.group(1))
                    continue

                if month_num is not None and current_year is not None:
                    day = last_day_month(year=current_year, month=month_num)
                    date_val = datetime.date(current_year, month_num, day)
                    fecha_str = date_val.strftime(format)

                    for c_idx, dept in enumerate(dept_cols):
                        val = splited_df.iloc[idx, c_idx + 1]
                        records.append({
                            "nv1": dept,
                            "fecha": fecha_str,
                            "valor": val
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

Executor_D_BO_000000019_01 = D_BO_000000019_01
Robot = D_BO_000000019_01
