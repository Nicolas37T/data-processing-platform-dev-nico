from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import datetime
import pandas as pd
import numpy as np
import xlrd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000052_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000052_01.
    Extracts financial data from Excel using xlrd to evaluate formatting,
    maintains a hierarchical structure (nv1, nv2, nv3, nv4), and returns
    data in a melted format.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format_str: str = "%Y-%m-%d"
    ) -> tuple:
        """
        Reads the Excel file, identifies the hierarchical structure based on
        indentation and leading spaces, and returns metadata alongside a
        melted pandas DataFrame.
        """
        try:
            # Use xlrd to preserve cell indentation and formatting properties
            wb = xlrd.open_workbook(file_path, formatting_info=True)
            sheet = wb.sheet_by_index(0)

            # Locate the "ACTIVO" row to define the start of the table headers
            header_row_idx = None
            for rowx in range(20):
                val = sheet.cell_value(rowx, 0)
                if isinstance(val, str) and val.strip().upper() == "ACTIVO":
                    header_row_idx = rowx - 1
                    break

            if header_row_idx is None:
                raise ValueError("Could not find 'ACTIVO' anchor row.")

            # Extract entity headers (e.g., AWM, AIS, ALT, TOTAL SISTEMA)
            entities = []
            col_indices = []
            for colx in range(1, sheet.ncols):
                val = sheet.cell_value(header_row_idx, colx)
                if isinstance(val, str) and val.strip():
                    entities.append(val.strip())
                    col_indices.append(colx)

            # Extract report titles located above the main table
            titles = []
            for rowx in range(header_row_idx):
                val = sheet.cell_value(rowx, 0)
                if isinstance(val, str) and val.strip():
                    titles.append(val.strip())

            # Extract report date from filename or use current date
            file_name = os.path.basename(file_path)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
            if date_match:
                report_date = date_match.group(1)
            else:
                report_date = datetime.datetime.now().strftime(format_str)

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number)
            }

            data = []
            main_roots = [
                'ACTIVO', 'PASIVO', 'PATRIMONIO',
                'PASIVO Y PATRIMONIO',
                'CUENTAS CONTINGENTES DEUDORAS',
                'CUENTAS DE ORDEN DEUDORAS'
            ]

            current_nv1 = None
            current_nv2 = None
            current_nv3 = None
            in_income_statement = False

            def next_row_has_spaces(curr_rowx: int) -> bool:
                """
                Lookahead function to determine if the immediately following
                valid row has indentation (indicating a child node).
                """
                for rx in range(curr_rowx + 1, sheet.nrows):
                    cval = sheet.cell_value(rx, 0)
                    if isinstance(cval, str) and cval.strip():
                        num_spaces = len(cval) - len(cval.lstrip())
                        return num_spaces >= 7
                return False

            for rowx in range(header_row_idx + 1, sheet.nrows):
                cell = sheet.cell(rowx, 0)
                val = cell.value

                if not isinstance(val, str) or not val.strip():
                    continue

                val_str = str(val)
                val_clean = val_str.strip()

                # Stop execution when the end of the first table is reached
                if "MERCADERÍA ALMACENADA" in val_clean.upper() or \
                   "MERCADERIA ALMACENADA" in val_clean.upper():
                    break

                # Ignore TOTAL rows to prevent double counting in vertical validation
                if val_clean.upper().startswith("TOTAL"):
                    continue

                spaces = len(val_str) - len(val_str.lstrip())
                xf = wb.xf_list[cell.xf_index]
                indent = xf.alignment.indent_level

                # State Machine for dynamic hierarchy assignment (nv1, nv2, nv3)
                if val_clean in main_roots:
                    current_nv1 = val_clean
                    current_nv2 = None
                    current_nv3 = None
                else:
                    is_sign = (
                        val_clean.startswith('(+)') or
                        val_clean.startswith('(-)') or
                        val_clean.startswith('(+/-)')
                    )

                    if is_sign:
                        in_income_statement = True
                        if next_row_has_spaces(rowx):
                            current_nv2 = val_clean
                            current_nv3 = None
                        else:
                            current_nv1 = val_clean
                            current_nv2 = None
                            current_nv3 = None
                    elif in_income_statement:
                        if spaces >= 7:
                            current_nv3 = val_clean
                        else:
                            current_nv2 = val_clean
                            current_nv3 = None
                    else:
                        # Standard Balance Sheet logic (Activo/Pasivo/Patrimonio)
                        if indent == 2 or spaces >= 7:
                            current_nv3 = val_clean
                        else:
                            current_nv2 = val_clean
                            current_nv3 = None

                # Extract numeric values across entity columns
                has_numeric_data = False
                row_data = {}
                for col_idx, entity in zip(col_indices, entities):
                    val_num = sheet.cell_value(rowx, col_idx)
                    if val_num != '' and val_num is not None:
                        try:
                            num = float(val_num)
                            row_data[entity] = num
                            has_numeric_data = True
                        except ValueError:
                            pass

                # Assemble valid rows into the final dataset
                if has_numeric_data:
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

            # Prevent scientific notation corruption (QA Bug #1)
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
        Validates the mathematical integrity of the extracted melted DataFrame.
        Performs horizontal (entities to total) and vertical (parent to child)
        reconciliations.
        Returns False if validation passes, True if discrepancies are found.
        """
        try:
            df = dataframe.copy()
            # Use native pandas to_numeric for clean floating point conversion
            df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
            has_errors = False

            # 1. Horizontal Reconciliation: Entity sum vs TOTAL SISTEMA (case-insensitive)
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

            # 2. Vertical Reconciliation: Root (nv1) vs direct children (nv2) (case-insensitive)
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
                    nv2_sum = df[nv2_mask]['valor'].sum()

                    if abs(root_total - nv2_sum) > TOLERANCE:
                        print(
                            f"Vertical error in {root} ({entity}): "
                            f"Total {root_total} != Sum nv2 {nv2_sum}"
                        )
                        has_errors = True

            # 3. Vertical Reconciliation: Subtotal (nv2) vs direct children (nv3)
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
        except Exception as e:
            print(f"Validation execution error: {e}")
            traceback.print_exc()
            return True

Executor_D_BO_000000052_01 = D_BO_000000052_01
Robot = D_BO_000000052_01
