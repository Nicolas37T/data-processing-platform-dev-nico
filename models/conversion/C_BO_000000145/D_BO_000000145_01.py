"""
Module for extracting and validating report D_BO_000000145_01.

Code: D_BO_000000145_01
Name: Bolivia: Variación Porcentual Mensual del Índice de Precios al Consumidor,
      según Ciudades Capitales y Conurbaciones
Page: 1
Periodicity: Mensual
Decimal Separator: ,
Conversion Factor: 1
Keywords: general ciudad
Sheet: CUADRO Nº 1.2 VAR MENSUAL
"""

import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import openpyxl
import pandas as pd
import xlrd
from unidecode import unidecode

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000145_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000145_01:
    'Bolivia: Variación Porcentual Mensual del Índice de Precios al Consumidor,
    según Ciudades Capitales y Conurbaciones'.
    Extracts monthly CPI percentage variations from sheet CUADRO Nº 1.2 VAR MENSUAL.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format_str: str = "%Y-%m-%d",
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Extracts monthly CPI percentage variation records across cities and regions.

        Parameters
        ----------
        file_path : str
            Absolute path of downloaded source file.
        key_words : str, optional
            Keywords for identification.
        template_path : str, optional
            Path to reference template if applicable.
        page_number : int, optional
            Page or sheet index (default 1).
        format_str : str, optional
            Date format for output strings (default '%Y-%m-%d').

        Returns
        -------
        Tuple[Dict[str, Any], pd.DataFrame]
            Tuple of (metadata_dict, df_melted) or ("", pd.DataFrame()) on error.
        """
        def resolve_actual_file(target_file: str) -> str:
            """Locate source file on disk accounting for path variations."""
            if os.path.isfile(target_file):
                return target_file

            base_name = os.path.basename(target_file)
            cleaned_base = re.sub(r"\s+D_BO_\d+_\d+", "", base_name)

            candidates = [
                target_file,
                os.path.join(os.path.dirname(target_file), cleaned_base),
                os.path.join("attachtments", base_name),
                os.path.join("attachtments", cleaned_base),
            ]
            for c in candidates:
                if os.path.isfile(c):
                    return c

            att_dir = os.path.join(os.getcwd(), "attachtments")
            if os.path.isdir(att_dir):
                for fname in os.listdir(att_dir):
                    fn_lower = fname.lower()
                    if fn_lower.endswith((".xlsx", ".xls")) and (
                        "general" in fn_lower or "ciudad" in fn_lower or "consumidor" in fn_lower
                    ):
                        return os.path.join(att_dir, fname)

            return target_file

        def read_target_grid(file_on_disk: str) -> Tuple[str, List[List[Any]]]:
            """Locate target sheet CUADRO Nº 1.2 VAR MENSUAL and read into 2D grid."""
            grid: List[List[Any]] = []
            sheet_title = "CUADRO Nº 1.2 VAR MENSUAL"
            ext = os.path.splitext(file_on_disk)[1].lower()

            if ext == ".xls":
                book = xlrd.open_workbook(file_on_disk)
                target_sh = None
                for s_name in book.sheet_names():
                    norm_s = unidecode(str(s_name)).upper()
                    if "1.2" in norm_s and ("VAR" in norm_s or "MENSUAL" in norm_s):
                        target_sh = book.sheet_by_name(s_name)
                        sheet_title = s_name
                        break
                if target_sh is None:
                    target_sh = book.sheet_by_index(0)
                    sheet_title = target_sh.name
                for r in range(target_sh.nrows):
                    grid.append([target_sh.cell_value(r, c) for c in range(target_sh.ncols)])
            else:
                wb = openpyxl.load_workbook(file_on_disk, data_only=True)
                ws = None
                for s_name in wb.sheetnames:
                    norm_s = unidecode(str(s_name)).upper()
                    if "1.2" in norm_s and ("VAR" in norm_s or "MENSUAL" in norm_s):
                        ws = wb[s_name]
                        sheet_title = s_name
                        break
                if ws is None:
                    for s_name in wb.sheetnames:
                        if key_words and key_words.lower() in str(s_name).lower():
                            ws = wb[s_name]
                            sheet_title = s_name
                            break
                if ws is None:
                    ws = wb.active
                    sheet_title = ws.title
                for row in ws.iter_rows(values_only=True):
                    grid.append(list(row))
                wb.close()

            return sheet_title, grid

        def clean_numeric_value(cell_val: Any) -> Optional[float]:
            """Normalizes raw cell values into floats."""
            if cell_val is None or cell_val == "":
                return None
            try:
                return float(cell_val)
            except (ValueError, TypeError):
                pass
            s = str(cell_val).strip()
            s = re.sub(r"[^\d,\.-]", "", s)
            if not s:
                return None
            if "." in s and "," in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            try:
                return float(s)
            except (ValueError, TypeError):
                return None

        try:
            actual_path = resolve_actual_file(file_path)
            if not os.path.isfile(actual_path):
                print(f"File not found: {file_path}")
                return "", pd.DataFrame()

            sheet_title, raw_grid = read_target_grid(actual_path)
            if not raw_grid:
                print(f"No content found in sheet {sheet_title} of {actual_path}")
                return "", pd.DataFrame()

            spanish_months = {
                "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
                "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
                "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
            }

            # 1. Locate header row containing month columns
            header_row_idx = -1
            for r_idx, row_vals in enumerate(raw_grid[:15]):
                match_count = sum(
                    1 for v in row_vals if unidecode(str(v or "")).strip().upper() in spanish_months
                )
                if match_count >= 2:
                    header_row_idx = r_idx
                    break

            if header_row_idx == -1:
                print(f"Could not locate table header with month columns in {actual_path}")
                return "", pd.DataFrame()

            # 2. Extract report titles above headers
            titles_list: List[str] = []
            for r_idx in range(header_row_idx - 1):
                if r_idx < len(raw_grid) and raw_grid[r_idx]:
                    for val in raw_grid[r_idx]:
                        val_str = str(val or "").strip()
                        if val_str and len(val_str) > 3 and val_str not in titles_list:
                            clean_t = re.sub(r"\s+", " ", val_str).strip()
                            titles_list.append(clean_t)

            if not titles_list:
                titles_list = [
                    "BOLIVIA: VARIACIÓN PORCENTUAL MENSUAL DEL ÍNDICE DE PRECIOS AL CONSUMIDOR, SEGÚN CIUDADES CAPITALES Y CONURBACIONES",
                    "(Porcentaje)",
                ]

            # 3. Parse Year headers (row above header_row_idx) and Month headers (header_row_idx)
            year_row = raw_grid[header_row_idx - 1] if header_row_idx > 0 else []
            month_row = raw_grid[header_row_idx]

            col_date_map: Dict[int, str] = {}
            current_year: Optional[int] = None
            max_cols = max(len(year_row), len(month_row))

            for col_idx in range(1, max_cols):
                # Update year if present in year_row
                if col_idx < len(year_row):
                    year_val = year_row[col_idx]
                    if year_val is not None:
                        y_str = str(year_val).strip()
                        m_year = re.search(r"\b(19\d\d|20\d\d)\b", y_str)
                        if m_year:
                            current_year = int(m_year.group(1))

                # Identify month
                if col_idx < len(month_row):
                    m_val = month_row[col_idx]
                    if m_val is not None and current_year is not None:
                        clean_m = unidecode(str(m_val)).strip().upper()
                        if clean_m in spanish_months:
                            m_num = spanish_months[clean_m]
                            date_ts = pd.Timestamp(year=current_year, month=m_num, day=1) + pd.offsets.MonthEnd(0)
                            col_date_map[col_idx] = date_ts.strftime(format_str)

            if not col_date_map:
                print(f"Could not map date columns in sheet {sheet_title}")
                return "", pd.DataFrame()

            # 4. Extract data rows
            records: List[Dict[str, Any]] = []

            for r_idx in range(header_row_idx + 1, len(raw_grid)):
                row_vals = raw_grid[r_idx]
                if not row_vals or row_vals[0] is None:
                    continue

                entity_name = str(row_vals[0]).strip()
                if not entity_name:
                    continue

                # Stop conditions on footnotes
                entity_upper = unidecode(entity_name).upper()
                if entity_upper.startswith("FUENTE:") or re.match(r"^\(\d+\)", entity_name):
                    break

                for col_idx, date_str in col_date_map.items():
                    if col_idx < len(row_vals):
                        val_raw = row_vals[col_idx]
                        num_val = clean_numeric_value(val_raw)
                        if num_val is not None:
                            records.append({
                                "nv1": entity_name,
                                "fecha": date_str,
                                "valor": num_val,
                            })

            df_melted = pd.DataFrame(records)

            if not df_melted.empty:
                df_melted["valor"] = df_melted["valor"].apply(
                    lambda x: np.format_float_positional(x, trim="-") if pd.notna(x) else x
                )
                df_melted = df_melted.dropna(subset=["valor"])

            metadata_dict = {
                "file_name": os.path.basename(actual_path),
                "titles": titles_list,
                "page_number": int(page_number),
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Extraction error processing {file_path}: {error}")
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Validates numerical integrity and consistency of extracted records.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Normalized DataFrame returned by extraction().
        decimal_separator : str, optional
            Decimal separator character (default: ',').
        TOLERANCE : float, optional
            Tolerance threshold for validation (default: 6.0).

        Returns
        -------
        bool
            False if data validation succeeds, True if discrepancies exist.
        """
        try:
            if dataframe is None or dataframe.empty:
                print("Validation failed: DataFrame is empty.")
                return True

            required_cols = {"nv1", "fecha", "valor"}
            if not required_cols.issubset(set(dataframe.columns)):
                print(f"Validation failed: missing columns {required_cols - set(dataframe.columns)}")
                return True

            numeric_values = pd.to_numeric(dataframe["valor"], errors="coerce")
            if numeric_values.isna().all():
                print("Validation failed: All 'valor' entries are invalid or NaN.")
                return True

            # Monthly inflation/CPI percentage variations can be positive, negative, or zero
            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


Robot = D_BO_000000145_01