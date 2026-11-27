from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import datetime
import calendar
import traceback
from typing import Tuple, Dict, Any, List
import pandas as pd
import numpy as np
import xlrd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000053_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000053_01:
    'Sociedades Controladoras de Grupos Financieros Estados Financieros por Entidad'.
    Processes ASFI sheet 13000, preserves hierarchical balance sheet and income
    statement dimensions (nv1, nv2, nv3, nv4), and returns normalized melted data.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format_str: str = "%Y-%m-%d"
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Extracts financial statement data from Excel using xlrd to evaluate
        indentation levels and cell alignment, establishing nv1, nv2, nv3 hierarchy
        across financial entities (nv4).
        """
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".xlsx":
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                target_sheet_name = None
                if "13000" in wb.sheetnames:
                    target_sheet_name = "13000"
                elif key_words:
                    for s_name in wb.sheetnames:
                        if key_words.lower() in s_name.lower():
                            target_sheet_name = s_name
                            break
                sheet = wb[target_sheet_name] if target_sheet_name else wb.active
                grid = [[cell.value for cell in row] for row in sheet.iter_rows()]
            else:
                wb = xlrd.open_workbook(file_path)
                target_sheet_name = None
                if "13000" in wb.sheet_names():
                    target_sheet_name = "13000"
                elif key_words:
                    for s_name in wb.sheet_names():
                        if key_words.lower() in s_name.lower():
                            target_sheet_name = s_name
                            break
                sheet = wb.sheet_by_name(target_sheet_name) if target_sheet_name else wb.sheet_by_index(0)
                grid = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]

            num_rows = len(grid)
            if num_rows == 0:
                raise ValueError("The worksheet is empty.")

            # Locate ACTIVO row to determine header row
            header_row_idx = None
            for rowx in range(min(25, num_rows)):
                val = grid[rowx][0] if len(grid[rowx]) > 0 else None
                if isinstance(val, str) and val.strip().upper() == "ACTIVO":
                    header_row_idx = rowx - 1
                    break

            if header_row_idx is None:
                # Fallback: search for row containing TOTAL SISTEMA
                for rowx in range(min(25, num_rows)):
                    row_vals = [
                        str(v).strip().upper()
                        for v in grid[rowx]
                        if v is not None
                    ]
                    if "TOTAL SISTEMA" in row_vals:
                        header_row_idx = rowx
                        break

            if header_row_idx is None:
                raise ValueError("Could not find table header or 'ACTIVO' row.")

            # Extract entity column headers (e.g. BNC, MCZ, INV, GFB, GAN, GFF, TOTAL SISTEMA)
            entities = []
            col_indices = []
            for colx in range(1, len(grid[header_row_idx])):
                val = grid[header_row_idx][colx]
                if isinstance(val, str) and val.strip():
                    entities.append(val.strip())
                    col_indices.append(colx)

            # Extract report titles above header
            titles = []
            for rowx in range(header_row_idx):
                val = grid[rowx][0] if len(grid[rowx]) > 0 else None
                if isinstance(val, str) and val.strip():
                    titles.append(val.strip())

            # Parse report cutoff date
            file_name = os.path.basename(file_path)
            report_date = None

            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
            if date_match:
                report_date = date_match.group(1)
            else:
                date_ym = re.search(r'(\d{4})(\d{2})', file_name)
                if date_ym:
                    year, month = int(date_ym.group(1)), int(date_ym.group(2))
                    last_day = calendar.monthrange(year, month)[1]
                    report_date = f"{year:04d}-{month:02d}-{last_day:02d}"

            if not report_date:
                month_map = {
                    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
                }
                for t in titles:
                    m = re.search(r'al\s+(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', t.lower())
                    if m:
                        day = int(m.group(1))
                        m_str = m.group(2)
                        year = int(m.group(3))
                        month_num = month_map.get(m_str, 1)
                        report_date = f"{year:04d}-{month_num:02d}-{day:02d}"
                        break

            if not report_date:
                report_date = datetime.datetime.now().strftime(format_str)

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number)
            }

            data = []
            main_roots = [
                'ACTIVO', 'PASIVO', 'PATRIMONIO',
                'PASIVO Y PATRIMONIO', 'PASIVO + PATRIMONIO',
                'CUENTAS CONTINGENTES DEUDORAS',
                'CUENTAS DE ORDEN DEUDORAS'
            ]

            current_nv1 = None
            current_nv2 = None
            current_nv3 = None
            in_income_statement = False

            # Scan rows starting from header_row_idx + 1
            for rowx in range(header_row_idx + 1, num_rows):
                val = grid[rowx][0] if len(grid[rowx]) > 0 else None

                if not isinstance(val, str) or not val.strip():
                    continue

                val_str = str(val)
                val_clean = val_str.strip()

                # Stop reading if end-of-report notes are encountered
                if "MERCADERÍA ALMACENADA" in val_clean.upper() or \
                   "MERCADERIA ALMACENADA" in val_clean.upper() or \
                   val_clean.upper().startswith("NOTAS:"):
                    break

                # Ignore duplicate TOTAL rows in Balance Sheet
                if val_clean.upper().startswith("TOTAL "):
                    continue

                spaces = len(val_str) - len(val_str.lstrip())

                # Hierarchy resolution
                if val_clean in main_roots:
                    in_income_statement = False
                    current_nv1 = val_clean
                    current_nv2 = None
                    current_nv3 = None
                elif in_income_statement or val_clean.startswith(('(+)', '(-)', '(=)', '(+/-)')):
                    in_income_statement = True
                    if val_clean.startswith(('(+)', '(-)', '(=)', '(+/-)')):
                        current_nv1 = val_clean
                        current_nv2 = None
                        current_nv3 = None
                    else:
                        if spaces >= 5:
                            current_nv3 = val_clean
                        else:
                            current_nv2 = val_clean
                            current_nv3 = None
                else:
                    if spaces >= 5:
                        current_nv3 = val_clean
                    else:
                        current_nv2 = val_clean
                        current_nv3 = None

                # Extract numeric values across entities
                has_numeric = False
                row_data = {}
                for col_idx, entity in zip(col_indices, entities):
                    val_num = grid[rowx][col_idx] if col_idx < len(grid[rowx]) else None
                    if val_num != '' and val_num is not None:
                        try:
                            num = float(val_num)
                            row_data[entity] = num
                            has_numeric = True
                        except (ValueError, TypeError):
                            pass

                if has_numeric:
                    for entity, num in row_data.items():
                        data.append({
                            'nv1': current_nv1,
                            'nv2': current_nv2,
                            'nv3': current_nv3,
                            'nv4': entity,
                            'fecha': report_date,
                            'valor': num
                        })

            df_melted = pd.DataFrame(data)

            if not df_melted.empty:
                df_melted['valor'] = df_melted['valor'].apply(
                    lambda x: np.format_float_positional(x, trim='-')
                    if pd.notna(x) else x
                )
                df_melted = df_melted.dropna(subset=['valor'])

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Extraction error processing {file_path}: {error}")
            traceback.print_exc()
            return {}, pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates mathematical consistency of the extracted DataFrame:
        1. Horizontal reconciliation: Entity columns sum equals TOTAL SISTEMA.
        2. Vertical reconciliation: Roots (ACTIVO, PASIVO, PATRIMONIO) equal
           the sum of direct child accounts.
        Returns False if validation succeeds, True if discrepancies are detected.
        """
        try:
            df = dataframe.copy()
            df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
            has_errors = False

            # 1. Horizontal check: Entity values sum to TOTAL SISTEMA
            grouped = df.groupby(['nv1', 'nv2', 'nv3', 'fecha'], dropna=False)
            for name, group in grouped:
                mask_total = group['nv4'].astype(str).str.strip().str.upper() == 'TOTAL SISTEMA'
                total_sistema = group[mask_total]['valor'].sum()
                entities_sum = group[~mask_total]['valor'].sum()

                if abs(total_sistema - entities_sum) > TOLERANCE:
                    print(
                        f"Horizontal error in {name}: "
                        f"Total System {total_sistema} != Entities Sum {entities_sum}"
                    )
                    has_errors = True

            # 2. Vertical check: Roots vs Level 2 children
            roots_to_check = ['ACTIVO', 'PASIVO', 'PATRIMONIO']
            for root in roots_to_check:
                for entity in df['nv4'].unique():
                    root_mask = (
                        (df['nv1'].astype(str).str.strip().str.upper() == root) &
                        (df['nv2'].isna()) &
                        (df['nv3'].isna()) &
                        (df['nv4'] == entity)
                    )
                    if not root_mask.any():
                        continue
                    root_total = df[root_mask]['valor'].sum()

                    nv2_mask = (
                        (df['nv1'].astype(str).str.strip().str.upper() == root) &
                        (df['nv2'].notna()) &
                        (df['nv3'].isna()) &
                        (df['nv4'] == entity)
                    )
                    if nv2_mask.any():
                        nv2_sum = df[nv2_mask]['valor'].sum()
                        if abs(root_total - nv2_sum) > TOLERANCE:
                            print(
                                f"Vertical error in {root} ({entity}): "
                                f"Total {root_total} != Sum nv2 {nv2_sum}"
                            )
                            has_errors = True

            # 3. Vertical check: Level 2 subtotals vs Level 3 sub-items
            nv2_groups = df[df['nv3'].notna()][['nv1', 'nv2', 'nv4', 'fecha']].drop_duplicates()
            for _, row in nv2_groups.iterrows():
                nv1, nv2, nv4, fecha = row['nv1'], row['nv2'], row['nv4'], row['fecha']

                nv2_mask = (
                    (df['nv1'] == nv1) &
                    (df['nv2'] == nv2) &
                    (df['nv3'].isna()) &
                    (df['nv4'] == nv4) &
                    (df['fecha'] == fecha)
                )
                if not nv2_mask.any():
                    continue
                nv2_total = df[nv2_mask]['valor'].sum()

                nv3_mask = (
                    (df['nv1'] == nv1) &
                    (df['nv2'] == nv2) &
                    (df['nv3'].notna()) &
                    (df['nv4'] == nv4) &
                    (df['fecha'] == fecha)
                )
                nv3_sum = df[nv3_mask]['valor'].sum()

                if abs(nv2_total - nv3_sum) > TOLERANCE:
                    print(
                        f"Vertical error in {nv2} ({nv4}): "
                        f"Total {nv2_total} != Sum nv3 {nv3_sum}"
                    )
                    has_errors = True

            return has_errors

        except Exception as error:
            print(f"Validation execution error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000053_01 = D_BO_000000053_01
Robot = D_BO_000000053_01
