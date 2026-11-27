from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import calendar
import pandas as pd
import numpy as np
from unidecode import unidecode

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000410_01(Conversion_Base):
    """
    Conversion robot for D_BO_000000410_01:
    Bolivia: Indice de Consumo de Agua Potable por Categoria segun Ano y Mes.
    Extracts tabular time-series data, flattening it to a normalized melted DataFrame.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> tuple:
        """
        Locates and extracts the potable water consumption index table from Excel.
        Returns a tuple of (metadata_dict, df_melted) with columns [nv1, nv2, nv3, fecha, valor].
        """
        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_idx = (page_number - 1) if (0 <= page_number - 1 < len(excel_file.sheet_names)) else 0
            df_raw = pd.read_excel(excel_file, sheet_name=sheet_idx, header=None)

            # Clean file name from any embedded ticket IDs
            raw_filename = os.path.basename(file_path)
            clean_filename = re.sub(r"\s+D_BO_\d+_\d+", "", raw_filename)

            # 1. Locate the anchor header row containing 'PERIODO' and 'INDICE GENERAL'
            header_row_idx = None
            for r in range(min(12, len(df_raw))):
                row_vals = [unidecode(str(v).lower()) for v in df_raw.iloc[r] if pd.notna(v)]
                if any("periodo" in v for v in row_vals) and any("indice general" in v for v in row_vals):
                    header_row_idx = r
                    break

            if header_row_idx is None:
                raise ValueError("Could not find table header row with 'PERIODO' anchor.")

            # 2. Extract metadata titles from non-empty rows preceding the header row
            titles = []
            for r in range(header_row_idx):
                row_text = []
                for val in df_raw.iloc[r]:
                    if pd.notna(val) and isinstance(val, str) and val.strip():
                        txt = val.strip()
                        if txt not in row_text:
                            row_text.append(txt)
                if row_text:
                    titles.append(" ".join(row_text))

            metadata_dict = {
                "file_name": clean_filename,
                "titles": titles,
                "page_number": int(page_number)
            }

            # 3. Dynamic column header mapping (nv1 and nv2)
            row_top = df_raw.iloc[header_row_idx]
            row_sub = df_raw.iloc[header_row_idx + 1]

            period_col_idx = 1
            col_mapping = []
            current_category_group = None

            for col_idx in range(period_col_idx + 1, df_raw.shape[1]):
                val_top = row_top[col_idx]
                val_sub = row_sub[col_idx]

                if pd.notna(val_top) and str(val_top).strip():
                    current_category_group = str(val_top).strip()

                if pd.notna(val_sub) and str(val_sub).strip():
                    sub_category_name = str(val_sub).strip()
                    # Categories (Residencial, Comercial, etc.) belong to nv1='CATEGORÍA'
                    norm_group = unidecode(current_category_group.upper()) if current_category_group else ""
                    nv1 = current_category_group if "INDICE GENERAL" not in norm_group else None
                    nv2 = sub_category_name
                    col_mapping.append((col_idx, nv1, nv2))
                elif pd.notna(val_top) and str(val_top).strip():
                    # Direct top level metric without subcategory (e.g., 'ÍNDICE GENERAL')
                    nv1 = None
                    nv2 = str(val_top).strip()
                    col_mapping.append((col_idx, nv1, nv2))

            # 4. Map Spanish month names for dynamic calendar date resolution
            month_map = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
            }

            current_year = None
            melted_records = []

            # 5. Iterate through tabular records
            for r in range(header_row_idx + 2, len(df_raw)):
                period_val = df_raw.iloc[r, period_col_idx]
                if pd.isna(period_val):
                    continue

                period_str = str(period_val).strip()
                norm_period = unidecode(period_str.lower())

                # Prevent double-counting and ignore footnote/source rows
                if (
                    norm_period.startswith("total")
                    or norm_period.startswith("fuente:")
                    or norm_period.startswith("(p)")
                ):
                    continue

                year_match = re.search(r"\b(19\d\d|20\d\d)\b", period_str)
                is_month = norm_period in month_map

                if not is_month and year_match:
                    current_year = int(year_match.group(1))
                    date_str = f"{current_year}-12-31"
                    nv3_val = period_str
                elif is_month and current_year is not None:
                    month_num = month_map[norm_period]
                    last_day = calendar.monthrange(current_year, month_num)[1]
                    date_str = f"{current_year}-{month_num:02d}-{last_day:02d}"
                    nv3_val = period_str
                else:
                    continue

                # Extract metric values across columns
                for col_idx, nv1, nv2 in col_mapping:
                    raw_val = df_raw.iloc[r, col_idx]
                    if pd.notna(raw_val):
                        melted_records.append({
                            "nv1": nv1,
                            "nv2": nv2,
                            "nv3": nv3_val,
                            "fecha": date_str,
                            "valor": raw_val
                        })

            df_melted = pd.DataFrame(melted_records)

            if df_melted.empty:
                raise ValueError("Extracted dataset is empty after flattening.")

            # 6. Numeric cleaning and QA scientific notation suppression
            df_melted["valor"] = pd.to_numeric(df_melted["valor"], errors="coerce")
            df_melted = df_melted.dropna(subset=["valor"])
            df_melted["valor"] = df_melted["valor"].apply(
                lambda x: np.format_float_positional(x, trim="-") if pd.notna(x) else x
            )

            # Ensure all categorical and date columns are strings or NaN
            for col in ["nv1", "nv2", "nv3", "fecha"]:
                df_melted[col] = df_melted[col].apply(
                    lambda x: str(x) if pd.notna(x) else np.nan
                )

            return (metadata_dict, df_melted)

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
        Validates consistency and numeric integrity of the extracted report.
        For price/consumption weighted index numbers, there are no printable arithmetic
        sums across categories. Returns False upon successful integrity checks.
        """
        try:
            if dataframe is None or dataframe.empty:
                return True

            if "valor" not in dataframe.columns:
                return True

            numeric_values = pd.to_numeric(dataframe["valor"], errors="coerce")
            if numeric_values.isna().all():
                return True

            return False
        except Exception as error:
            print(f"Error during validation: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000410_01 = D_BO_000000410_01
Robot = D_BO_000000410_01
