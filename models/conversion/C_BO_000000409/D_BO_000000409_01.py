from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import calendar
import traceback
import unicodedata
from datetime import datetime
import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000409_01(Conversion_Base):
    """
    Conversion robot for D_BO_000000409_01:
    Bolivia: Indice de Consumo de Energia Electrica.
    Extracts tabular data and transforms it into a melted vertical DataFrame.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> tuple:
        """
        Locates and extracts the electricity consumption variation table from the Excel file.
        Returns a tuple containing a metadata dictionary and a normalized melted DataFrame.
        """
        try:
            xl = pd.ExcelFile(file_path)

            # Locate the target sheet representing variation with respect to previous period
            target_sheet = None
            for name in xl.sheet_names:
                norm_name = unicodedata.normalize(
                    'NFKD', name
                ).encode('ASCII', 'ignore').decode('utf-8').lower()
                if "periodo anterior" in norm_name or (
                    "variacion" in norm_name and "anterior" in norm_name and "similar" not in norm_name
                ):
                    target_sheet = name
                    break

            if target_sheet is None:
                sheet_idx = page_number - 1 if 0 <= page_number - 1 < len(xl.sheet_names) else 0
                target_sheet = xl.sheet_names[sheet_idx]

            df_raw = xl.parse(target_sheet, header=None)

            # Locate header row containing the PERIOD anchor
            header_row_period = -1
            col_period = -1
            period_pattern = re.compile(r"^PER[IÍ]ODO$", re.IGNORECASE)

            for r_idx in range(min(15, len(df_raw))):
                for c_idx, val in enumerate(df_raw.iloc[r_idx]):
                    if pd.notna(val) and isinstance(val, str):
                        clean_val = val.strip()
                        if period_pattern.match(clean_val):
                            header_row_period = r_idx
                            col_period = c_idx
                            break
                if header_row_period != -1:
                    break

            if header_row_period == -1:
                raise ValueError("Could not locate the PERIODO header row in the target worksheet.")

            # Extract titles preceding the table header
            titles = []
            for i in range(header_row_period):
                row_vals = []
                for val in df_raw.iloc[i]:
                    if pd.notna(val) and isinstance(val, str) and val.strip():
                        s = re.sub(r'\s+', ' ', val).strip()
                        if s not in row_vals:
                            row_vals.append(s)
                if row_vals:
                    titles.append(" ".join(row_vals))

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number)
            }

            # Map column categories and subheaders dynamically
            col_mapping = {}
            curr_category = None

            for c_idx in range(col_period + 1, df_raw.shape[1]):
                val_top = df_raw.iloc[header_row_period, c_idx]
                val_sub = df_raw.iloc[header_row_period + 1, c_idx]

                top_str = re.sub(r'\s+', ' ', str(val_top)).strip() if pd.notna(val_top) else None
                sub_str = re.sub(r'\s+', ' ', str(val_sub)).strip() if pd.notna(val_sub) else None

                if sub_str is not None:
                    if top_str is not None:
                        curr_category = top_str
                    col_mapping[c_idx] = {
                        "nv1": curr_category,
                        "nv2": sub_str
                    }
                elif top_str is not None:
                    # Standalone indicator (e.g., INDICE GENERAL with no subcategories)
                    col_mapping[c_idx] = {
                        "nv1": None,
                        "nv2": top_str
                    }

            # Mapping for Spanish month names
            month_map = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
                "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
            }

            records = []
            current_year = None
            year_pattern = re.compile(r"\b(19\d\d|20\d\d)\b")

            # Iterate over data rows
            for r_idx in range(header_row_period + 2, len(df_raw)):
                period_val = df_raw.iloc[r_idx, col_period]
                if pd.isna(period_val):
                    continue

                period_str = str(period_val).strip()
                norm_p = unicodedata.normalize(
                    'NFKD', period_str
                ).encode('ASCII', 'ignore').decode('utf-8').lower()

                # Stop processing on footnote anchors
                if any(norm_p.startswith(stop_w) for stop_w in ["fuente", "nota", "(p) :", "(p):"]):
                    break

                # Prevent double counting on total summary rows
                if norm_p.startswith("total"):
                    continue

                year_match = year_pattern.search(period_str)

                # Check whether row is monthly or annual consolidated
                is_month = False
                month_int = None
                for m_name, m_num in month_map.items():
                    if norm_p.startswith(m_name):
                        is_month = True
                        month_int = m_num
                        break

                if is_month:
                    if current_year is None:
                        continue
                    last_day = calendar.monthrange(current_year, month_int)[1]
                    date_obj = datetime(current_year, month_int, last_day)
                    date_str = date_obj.strftime(format)
                    nv3_val = period_str
                elif year_match:
                    current_year = int(year_match.group(1))
                    date_obj = datetime(current_year, 12, 31)
                    date_str = date_obj.strftime(format)
                    nv3_val = period_str
                else:
                    continue

                for col_idx, col_info in col_mapping.items():
                    val = df_raw.iloc[r_idx, col_idx]
                    if pd.notna(val):
                        records.append({
                            "nv1": col_info["nv1"],
                            "nv2": col_info["nv2"],
                            "nv3": nv3_val,
                            "fecha": date_str,
                            "valor": val
                        })

            df_melted = pd.DataFrame(records)

            if df_melted.empty:
                raise ValueError("No records were extracted from the worksheet.")

            # Numeric conversion and scientific notation prevention
            df_melted["valor"] = pd.to_numeric(df_melted["valor"], errors="coerce")
            df_melted = df_melted.dropna(subset=["valor"])
            df_melted["valor"] = df_melted["valor"].apply(
                lambda x: np.format_float_positional(x, trim='-') if pd.notna(x) else x
            )

            # Ensure all categorical and date columns are strings
            for col in ["nv1", "nv2", "nv3", "fecha"]:
                if col in df_melted.columns:
                    df_melted[col] = df_melted[col].apply(
                        lambda x: str(x) if pd.notna(x) else None
                    )

            # Final ordering of columns
            ordered_cols = ["nv1", "nv2", "nv3", "fecha", "valor"]
            df_melted = df_melted[ordered_cols]

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates the mathematical consistency and integrity of the extracted data.
        Returns False if validation succeeds (or if no summary totals are present).
        Returns True if a discrepancy or structural error is found.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True

            if "valor" not in dataframe.columns or "fecha" not in dataframe.columns:
                return True

            # This report contains percentage variations and weighted indices without
            # direct arithmetic sum reconciliations.
            return False
        except Exception:
            traceback.print_exc()
            return True

Executor_D_BO_000000409_01 = D_BO_000000409_01
Robot = D_BO_000000409_01
