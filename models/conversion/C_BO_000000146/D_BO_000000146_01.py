from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
import pandas as pd
import numpy as np
import xlrd
from unidecode import unidecode

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000146_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000146_01:
    'Bolivia: Índice de Volumen de Producción de Minerales por Tipo de Mineral, según Año y Mes'.
    Extracts monthly mineral production index records across mineral commodities (nv1).
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
        Extracts monthly mineral production indices from INE Excel files.

        Parameters
        ----------
        file_path : str
            Absolute path to source Excel file.
        key_words : str, optional
            Keywords for filtering.
        template_path : str, optional
            Path to reference template if applicable.
        page_number : int, optional
            Target sheet number (1-indexed).
        format_str : str, optional
            Date format for output strings (default: '%Y-%m-%d').

        Returns
        -------
        Tuple[Dict[str, Any], pd.DataFrame]
            Metadata dictionary and normalized melted DataFrame.
        """
        def resolve_actual_file(target_file: str) -> str:
            """Locates the source file on disk accounting for path and name variations."""
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
                        "indice" in fn_lower or "volumen" in fn_lower or "mineral" in fn_lower
                    ):
                        return os.path.join(att_dir, fname)

            return target_file

        def read_sheet_grid(file_on_disk: str, target_page: int) -> List[List[Any]]:
            """Reads sheet rows into a 2D matrix supporting both xls and xlsx formats."""
            grid: List[List[Any]] = []
            ext = os.path.splitext(file_on_disk)[1].lower()

            if ext == ".xls":
                book = xlrd.open_workbook(file_on_disk)
                s_idx = target_page - 1 if target_page <= book.nsheets else 0
                sh = book.sheet_by_index(s_idx)
                for r in range(sh.nrows):
                    grid.append([sh.cell_value(r, c) for c in range(sh.ncols)])
            else:
                wb = openpyxl.load_workbook(file_on_disk, data_only=True)
                s_name = wb.sheetnames[target_page - 1] if target_page <= len(wb.sheetnames) else wb.sheetnames[0]
                ws = wb[s_name]
                for row in ws.iter_rows(values_only=True):
                    grid.append(list(row))

            return grid

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

            raw_grid = read_sheet_grid(actual_path, page_number)
            if not raw_grid:
                print(f"No content found in {actual_path}")
                return "", pd.DataFrame()

            spanish_months = {
                "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
                "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
                "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
            }

            # 1. Locate header row containing 'PERIODO'
            header_row_idx = -1
            periodo_col_idx = -1
            mineral_cols: Dict[int, str] = {}

            for r_idx, row_vals in enumerate(raw_grid[:15]):
                for c_idx, val in enumerate(row_vals):
                    clean_str = unidecode(str(val or "")).strip().upper()
                    if clean_str == "PERIODO":
                        header_row_idx = r_idx
                        periodo_col_idx = c_idx
                        break
                if header_row_idx != -1:
                    break

            if header_row_idx == -1:
                print(f"Could not locate 'PERIODO' header in {actual_path}")
                return "", pd.DataFrame()

            # 2. Extract mineral column names following PERIODO
            header_row = raw_grid[header_row_idx]
            for c_idx in range(periodo_col_idx + 1, len(header_row)):
                col_name_raw = str(header_row[c_idx] or "").strip()
                if col_name_raw:
                    clean_name = re.sub(r"\s+", " ", col_name_raw).strip()
                    mineral_cols[c_idx] = clean_name

            if not mineral_cols:
                print(f"Could not locate mineral columns in {actual_path}")
                return "", pd.DataFrame()

            # 3. Extract report titles above header
            titles_list: List[str] = []
            for r_idx in range(header_row_idx):
                for val in raw_grid[r_idx]:
                    val_str = str(val or "").strip()
                    if val_str and len(val_str) > 3:
                        clean_t = re.sub(r"\s+", " ", val_str).strip()
                        if clean_t and clean_t not in titles_list:
                            titles_list.append(clean_t)

            if not titles_list:
                titles_list = [
                    "BOLIVIA: ÍNDICE DE VOLUMEN DE PRODUCCIÓN DE MINERALES, POR TIPO DE MINERAL SEGÚN MES, 2017 - 2026",
                    "(Año de referencia 2017 - Base Móvil)",
                ]

            # 4. Iterate data rows and extract monthly records
            rows_list: List[Dict[str, Any]] = []
            current_year: Optional[int] = None

            for r_idx in range(header_row_idx + 1, len(raw_grid)):
                row_vals = raw_grid[r_idx]
                if periodo_col_idx >= len(row_vals):
                    continue

                period_cell = row_vals[periodo_col_idx]
                if period_cell is None:
                    continue

                period_str = str(period_cell).strip()
                if not period_str:
                    continue

                # Stop conditions on footnotes
                period_upper = unidecode(period_str).upper()
                if period_upper.startswith("FUENTE:") or period_upper.startswith("(P):"):
                    break

                # Detect year header (e.g. '2025', '2026(p)')
                year_match = re.search(r"^(19\d\d|20\d\d)", period_str)
                if year_match:
                    current_year = int(year_match.group(1))
                    # Annual totals / preliminary headers are skipped for monthly series
                    continue

                # Detect month row
                clean_month_key = unidecode(period_str).strip().upper()
                if clean_month_key in spanish_months and current_year is not None:
                    month_num = spanish_months[clean_month_key]
                    date_ts = pd.Timestamp(year=current_year, month=month_num, day=1) + pd.offsets.MonthEnd(0)
                    date_str = date_ts.strftime(format_str)

                    for col_idx, mineral_name in mineral_cols.items():
                        if col_idx < len(row_vals):
                            raw_val = row_vals[col_idx]
                            num_val = clean_numeric_value(raw_val)
                            if num_val is not None:
                                rows_list.append({
                                    "nv1": mineral_name,
                                    "fecha": date_str,
                                    "valor": num_val,
                                })

            df_melted = pd.DataFrame(rows_list)
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
        Validates data consistency and numeric integrity of extracted records.

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

            # Production index values must be non-negative
            if (numeric_values < 0).any():
                print("Validation failed: Negative index values detected.")
                return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000146_01 = D_BO_000000146_01
Robot = D_BO_000000146_01
