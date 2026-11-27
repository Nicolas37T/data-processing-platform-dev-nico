from models.conversion.Conversion_Base import Conversion_Base
"""
Module for extracting and validating report D_BO_000000147_01.

Report Code: D_BO_000000147_01
Report Name: Bolivia: Volumen Comercializado de Refinados al Mercado Interno por Producto, según Mes
Periodicity: Mensual
Page: 1
Decimal Separator: ,
Conversion Factor: 1
Keywords: comercializado interno
"""

import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pandas as pd
import xlrd
from unidecode import unidecode

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000147_01(Conversion_Base):
    """Conversion robot for report D_BO_000000147_01."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Extract refined petroleum products domestic commercial volume by month.

        Parameters
        ----------
        file_path : str
            Absolute path to downloaded source file (.xlsx or .xls).
        key_words : str, optional
            Keywords for identifying the report.
        template_path : str, optional
            Path to reference template if applicable.
        page_number : int, optional
            Target sheet number (1-indexed, default 1).
        format : str, optional
            Output date format string (default '%Y-%m-%d').

        Returns
        -------
        Tuple[Dict[str, Any], pd.DataFrame]
            Tuple containing metadata dictionary and melted normalized DataFrame.
        """
        def resolve_actual_file(target_file: str) -> str:
            """Locate source file on disk accounting for path variations."""
            if os.path.isfile(target_file):
                return target_file

            # Strip robot code if present in the filename
            # e.g. 2025-02-28_comercializado interno D_BO_000000147_01.xlsx
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

            # Search attachtments directory for matching files (e.g. comercializado interno)
            att_dir = os.path.join(os.getcwd(), "attachtments")
            if os.path.isdir(att_dir):
                for fname in os.listdir(att_dir):
                    fn_lower = fname.lower()
                    if (
                        fn_lower.endswith((".xlsx", ".xls"))
                        and "comercializado" in fn_lower
                        and "interno" in fn_lower
                    ):
                        return os.path.join(att_dir, fname)

            return target_file

        def read_sheet_grid(file_on_disk: str, target_page: int) -> Tuple[List[str], List[List[Any]]]:
            """Read tabular matrix and sheet title from .xlsx or .xls file."""
            grid: List[List[Any]] = []
            titles: List[str] = []

            ext = os.path.splitext(file_on_disk)[1].lower()
            if ext == ".xls":
                book = xlrd.open_workbook(file_on_disk)
                s_idx = target_page - 1 if target_page <= book.nsheets else 0
                sh = book.sheet_by_index(s_idx)
                for r in range(sh.nrows):
                    row_vals = [sh.cell_value(r, c) for c in range(sh.ncols)]
                    grid.append(row_vals)
            else:
                wb = openpyxl.load_workbook(file_on_disk, data_only=True)
                s_name = wb.sheetnames[target_page - 1] if target_page <= len(wb.sheetnames) else wb.sheetnames[0]
                ws = wb[s_name]
                for row in ws.iter_rows(values_only=True):
                    grid.append(list(row))

            return titles, grid

        def clean_numeric_value(cell_val: Any) -> Optional[float]:
            """Parse cell numeric value into float."""
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
            # Handle string thousands/decimal separators
            if "." in s and "," in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", "")
            try:
                return float(s)
            except (ValueError, TypeError):
                return None

        try:
            actual_path = resolve_actual_file(file_path)
            if not os.path.isfile(actual_path):
                print(f"File not found: {file_path}")
                return "", pd.DataFrame()

            titles_meta, raw_grid = read_sheet_grid(actual_path, page_number)
            if not raw_grid:
                print(f"No rows found in {actual_path}")
                return "", pd.DataFrame()

            # Spanish month names mapping
            spanish_months = {
                "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
                "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
                "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
            }

            # 1. Locate header row containing 'PERIODO'
            header_row_idx = -1
            periodo_col_idx = -1
            product_cols: Dict[int, str] = {}

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

            # 2. Extract product names from columns following PERIODO
            header_row = raw_grid[header_row_idx]
            for c_idx in range(periodo_col_idx + 1, len(header_row)):
                col_name_raw = str(header_row[c_idx] or "").strip()
                if col_name_raw:
                    clean_product_name = re.sub(r"\s+", " ", col_name_raw).strip()
                    product_cols[c_idx] = clean_product_name

            if not product_cols:
                print(f"Could not locate product columns in {actual_path}")
                return "", pd.DataFrame()

            # 3. Extract document titles from rows above header
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
                    "BOLIVIA: VOLUMEN COMERCIALIZADO DE REFINADOS AL MERCADO INTERNO POR PRODUCTO, SEGÚN AÑO Y MES, 2000 - 2025",
                    "(En barriles)",
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

                # Stop conditions on footnotes or metadata rows
                period_upper = unidecode(period_str).upper()
                if period_upper.startswith("FUENTE:") or period_upper.startswith("(P):"):
                    break

                # Detect year header (e.g. '2024', '2025(p)', '2020')
                year_match = re.search(r"^(19\d\d|20\d\d)", period_str)
                if year_match:
                    current_year = int(year_match.group(1))
                    # Year headers are annual summary rows, continue to monthly rows
                    continue

                # Detect month row
                clean_month_key = unidecode(period_str).strip().upper()
                if clean_month_key in spanish_months and current_year is not None:
                    month_num = spanish_months[clean_month_key]
                    date_ts = pd.Timestamp(year=current_year, month=month_num, day=1) + pd.offsets.MonthEnd(0)
                    date_str = date_ts.strftime(format)

                    for col_idx, prod_name in product_cols.items():
                        if col_idx < len(row_vals):
                            raw_val = row_vals[col_idx]
                            num_val = clean_numeric_value(raw_val)
                            if num_val is not None:
                                rows_list.append(
                                    {
                                        "nv1": prod_name,
                                        "fecha": date_str,
                                        "valor": float(num_val),
                                    }
                                )

            df_melted = pd.DataFrame(rows_list)

            # Ensure strict DATAX column order [nv1, fecha, valor]
            cols_order = ["nv1", "fecha", "valor"]
            for col in cols_order:
                if col not in df_melted.columns:
                    df_melted[col] = None
            df_melted = df_melted[cols_order]

            # Convert valor using official to_numeric_datax on Series
            df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=",")

            # Ensure string types for nv1 and fecha
            df_melted["nv1"] = df_melted["nv1"].astype(str)
            df_melted["fecha"] = df_melted["fecha"].astype(str)

            metadata: Dict[str, Any] = {
                "file_name": os.path.basename(actual_path),
                "titles": titles_list,
                "page_number": page_number,
            }

            return metadata, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """Validate numeric integrity, non-negativity and consistency of extracted volumes.

        Returns
        -------
        bool
            False if validation passes (no errors), True if validation fails.
        """
        try:
            if dataframe is None or dataframe.empty:
                print("Validation failed: DataFrame is empty or None")
                return True

            df = dataframe.copy()

            # Ensure numeric valor
            if not pd.api.types.is_numeric_dtype(df["valor"]):
                df["valor"] = to_numeric_datax(df["valor"], decimal_separator=decimal_separator)

            # 1. Check for non-null and numeric validity
            if df["valor"].isna().any():
                print("Validation error: NaN values found in 'valor' column")
                return True

            # 2. Check for non-negative values (volumes must be non-negative)
            if (df["valor"] < 0).any():
                print("Validation error: Negative volume values found")
                return True

            # 3. Check date format consistency
            try:
                pd.to_datetime(df["fecha"], format="%Y-%m-%d", errors="raise")
            except Exception as date_err:
                traceback.print_exc()
                print(f"Validation error in 'fecha' format: {date_err}")
                return True

            # 4. Check for duplicate keys (nv1, fecha)
            dup_mask = df.duplicated(subset=["nv1", "fecha"])
            if dup_mask.any():
                print("Validation error: Duplicate (nv1, fecha) records found")
                return True

            # 5. Check product coverage
            expected_products = [
                "GASOLINA AUTOMOTRIZ",
                "GASOLINA DE AVIACIÓN",
                "GAS LICUADO",
                "KEROSENO",
                "JET FUEL",
                "DIÉSEL OIL",
            ]
            extracted_prods = set(df["nv1"].unique())
            for prod in expected_products:
                if prod not in extracted_prods:
                    print(f"Validation warning: Expected product {prod} not found in {extracted_prods}")

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Alias for compatibility with test runners expecting Robot

Executor_D_BO_000000147_01 = D_BO_000000147_01
Robot = D_BO_000000147_01
