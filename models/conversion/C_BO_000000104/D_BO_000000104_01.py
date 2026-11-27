from models.conversion.Conversion_Base import Conversion_Base
import calendar
import datetime
import os
import re
import traceback
import unicodedata
import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000104_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000104_01:
    'Origen de la Liquidez Total (Desagregado)'.
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
        Extracts liquidity origins report from Excel, normalizing multi-level
        hierarchical time series into a melted tabular format.

        Parameters
        ----------
        file_path : str
            Absolute path to the downloaded Excel file.
        key_words : str
            Keywords to identify the target report.
        template_path : str
            Path to reference template (if applicable).
        page_number : int
            Sheet index / page number (defaults to 1).
        format : str
            Target date format (defaults to '%Y-%m-%d').

        Returns
        -------
        tuple
            (metadata_dict, df_melted) where metadata_dict contains report
            metadata and df_melted contains [nv1, nv2, nv3, nv4, fecha, valor].
        """
        try:
            sheet_idx = page_number - 1 if page_number and page_number > 0 else 0
            df_raw = pd.read_excel(file_path, sheet_name=sheet_idx, header=None)

            # 1. Extract titles dynamically from header rows
            titles = []
            for r_idx in (2, 4):
                if r_idx < df_raw.shape[0]:
                    val = df_raw.iloc[r_idx, 0]
                    if pd.notna(val):
                        clean_t = re.sub(r'\s+', ' ', str(val)).strip()
                        clean_t = re.sub(r'\s*\(?\d+\)?$', '', clean_t)
                        clean_t = re.sub(r'\s+p$', '', clean_t)
                        if clean_t:
                            titles.append(clean_t)

            # Extract monetary unit from last column of row index 4 if present
            if df_raw.shape[0] > 4:
                last_cell = df_raw.iloc[4, -1]
                if pd.notna(last_cell):
                    clean_unit = re.sub(r'\s+', ' ', str(last_cell)).strip()
                    if clean_unit and clean_unit.startswith('('):
                        titles.append(clean_unit)

            if not titles:
                titles = [
                    "ORIGEN DE LA LIQUIDEZ TOTAL",
                    "DESAGREGADO",
                    "(En miles de bolivianos)"
                ]

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number)
            }

            # 2. Map date columns from row index 6 (7th row in Excel)
            spanish_months = {
                'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11,
                'dic': 12
            }

            date_row_idx = 6
            col_date_mapping = {}

            for col_idx in range(5, df_raw.shape[1]):
                cell_val = df_raw.iloc[date_row_idx, col_idx]
                if pd.isna(cell_val):
                    continue

                parsed_date = None
                if isinstance(cell_val, (datetime.datetime, datetime.date, pd.Timestamp)):
                    year = cell_val.year
                    month = cell_val.month
                    _, last_day = calendar.monthrange(year, month)
                    parsed_date = f"{year:04d}-{month:02d}-{last_day:02d}"
                elif isinstance(cell_val, str):
                    cell_str = cell_val.strip().lower()
                    match = re.search(r'([a-z]{3})[-.\s]*(\d{2,4})', cell_str)
                    if match:
                        month_token = match.group(1)
                        year_token = match.group(2)
                        year = int(year_token)
                        if year < 100:
                            year += 2000
                        month = spanish_months.get(month_token)
                        if month:
                            _, last_day = calendar.monthrange(year, month)
                            parsed_date = f"{year:04d}-{month:02d}-{last_day:02d}"

                if parsed_date:
                    col_date_mapping[col_idx] = parsed_date

            # 3. State machine to capture 4-level hierarchy without hardcoding
            records = []
            current_nv1 = None
            current_nv2 = None
            current_nv3 = None
            current_nv4 = None

            for row_idx in range(7, df_raw.shape[0]):
                c0 = df_raw.iloc[row_idx, 0]
                c1 = df_raw.iloc[row_idx, 1]
                c2 = df_raw.iloc[row_idx, 2]
                c3 = df_raw.iloc[row_idx, 3]
                c4 = df_raw.iloc[row_idx, 4]

                c0_clean = re.sub(r'\s+', ' ', str(c0)).strip() if pd.notna(c0) else ""

                # Stop reading at footnotes or metadata
                c0_upper = c0_clean.upper()
                if any(c0_upper.startswith(k) for k in [
                    "FUENTE", "ELABORACIÓN", "ELABORACION", "NOTA"
                ]):
                    break

                # Skip grand total / aggregate rows to avoid double counting
                if c0_upper.startswith("TOTAL") or re.match(r"^LIQUIDEZ\s+TOTAL", c0_clean, re.I):
                    continue

                # Update state machine based on column positions before evaluating data
                if c0_clean:
                    current_nv1 = c0_clean
                    current_nv2 = None
                    current_nv3 = None
                    current_nv4 = None
                elif pd.notna(c1) and str(c1).strip():
                    current_nv2 = re.sub(r'\s+', ' ', str(c1)).strip()
                    current_nv3 = None
                    current_nv4 = None
                elif pd.notna(c2) and str(c2).strip():
                    current_nv3 = re.sub(r'\s+', ' ', str(c2)).strip()
                    current_nv4 = None
                elif pd.notna(c4) and str(c4).strip():
                    current_nv4 = re.sub(r'\s+', ' ', str(c4)).strip()
                elif pd.notna(c3) and str(c3).strip():
                    current_nv4 = re.sub(r'\s+', ' ', str(c3)).strip()
                else:
                    continue

                # Extract time-series values across mapped date columns
                for col_idx, dt in col_date_mapping.items():
                    val = df_raw.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        try:
                            num_val = float(val)
                            records.append({
                                'nv1': current_nv1,
                                'nv2': current_nv2,
                                'nv3': current_nv3,
                                'nv4': current_nv4,
                                'fecha': dt,
                                'valor': num_val
                            })
                        except (ValueError, TypeError):
                            pass

            df_melted = pd.DataFrame(records)
            if df_melted.empty:
                return metadata_dict, pd.DataFrame(
                    columns=['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor']
                )

            # Round numeric values and prevent scientific notation formatting
            df_melted['valor'] = df_melted['valor'].round(2)
            df_melted['valor'] = df_melted['valor'].apply(
                lambda x: np.format_float_positional(x, trim='-') if pd.notna(x) else x
            )
            df_melted = df_melted.dropna(subset=['valor'])

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ({}, pd.DataFrame())

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates accounting consistency across hierarchical levels:
        1. Level 4 details sum to Level 3 parent (Depósitos).
        2. Level 3 accounts sum to Level 2 sub-sector (Gobierno Central, etc.).
        3. Level 2 sub-sectors sum to Level 1 chapter (Activos, Crédito, etc.).

        Parameters
        ----------
        dataframe : pd.DataFrame
            Extracted DataFrame with metadata or melted structure.
        decimal_separator : str
            Decimal separator character ('.' or ',').
        TOLERANCE : float
            Maximum allowable discrepancy (default: 6.0).

        Returns
        -------
        bool
            False if validation passes (no discrepancies), True if errors found.
        """
        try:
            if dataframe.empty or 'valor' not in dataframe.columns:
                return False

            df_check = dataframe.copy()

            # Parse numeric values safely
            df_check['valor_num'] = pd.to_numeric(df_check['valor'], errors='coerce')
            if df_check['valor_num'].isna().all():
                try:
                    df_check['valor_num'] = to_numeric_datax(
                        df_check['valor'], decimal_separator
                    )
                except Exception:
                    import traceback; traceback.print_exc()
                    pass

            # 1. Level 4 -> Level 3 validation
            l3_parents = df_check[df_check['nv3'].notna() & df_check['nv4'].isna()]
            l4_children = df_check[df_check['nv3'].notna() & df_check['nv4'].notna()]
            if not l3_parents.empty and not l4_children.empty:
                l4_sum = l4_children.groupby(
                    ['nv1', 'nv2', 'nv3', 'fecha']
                )['valor_num'].sum().reset_index()
                l4_sum.rename(columns={'valor_num': 'calc_val'}, inplace=True)
                merged_34 = pd.merge(
                    l3_parents, l4_sum, on=['nv1', 'nv2', 'nv3', 'fecha']
                )
                diff_34 = (merged_34['valor_num'] - merged_34['calc_val']).abs()
                if (diff_34 > TOLERANCE).any():
                    print(
                        f"Validation failure in Level 4 -> Level 3. "
                        f"Max diff: {diff_34.max()}"
                    )
                    return True

            # 2. Level 3 -> Level 2 validation
            l2_parents = df_check[
                df_check['nv2'].notna() & df_check['nv3'].isna() & df_check['nv4'].isna()
            ]
            l3_children = df_check[
                df_check['nv2'].notna() & df_check['nv3'].notna() & df_check['nv4'].isna()
            ]
            if not l2_parents.empty and not l3_children.empty:
                l3_sum = l3_children.groupby(
                    ['nv1', 'nv2', 'fecha']
                )['valor_num'].sum().reset_index()
                l3_sum.rename(columns={'valor_num': 'calc_val'}, inplace=True)
                merged_23 = pd.merge(
                    l2_parents, l3_sum, on=['nv1', 'nv2', 'fecha']
                )
                diff_23 = (merged_23['valor_num'] - merged_23['calc_val']).abs()
                if (diff_23 > TOLERANCE).any():
                    print(
                        f"Validation failure in Level 3 -> Level 2. "
                        f"Max diff: {diff_23.max()}"
                    )
                    return True

            # 3. Level 2 -> Level 1 validation
            l1_parents = df_check[
                df_check['nv1'].notna() & df_check['nv2'].isna() &
                df_check['nv3'].isna() & df_check['nv4'].isna()
            ]
            l2_children = df_check[
                df_check['nv1'].notna() & df_check['nv2'].notna() &
                df_check['nv3'].isna() & df_check['nv4'].isna()
            ]
            if not l1_parents.empty and not l2_children.empty:
                l2_sum = l2_children.groupby(
                    ['nv1', 'fecha']
                )['valor_num'].sum().reset_index()
                l2_sum.rename(columns={'valor_num': 'calc_val'}, inplace=True)
                merged_12 = pd.merge(
                    l1_parents, l2_sum, on=['nv1', 'fecha']
                )
                diff_12 = (merged_12['valor_num'] - merged_12['calc_val']).abs()
                if (diff_12 > TOLERANCE).any():
                    print(
                        f"Validation failure in Level 2 -> Level 1. "
                        f"Max diff: {diff_12.max()}"
                    )
                    return True

            return False

        except Exception as error:
            print(f"Error during validation: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000104_01 = D_BO_000000104_01
Robot = D_BO_000000104_01
