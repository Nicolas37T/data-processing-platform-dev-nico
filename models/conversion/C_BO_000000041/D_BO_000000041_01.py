from models.conversion.Conversion_Base import Conversion_Base
"""
Module for converting report D_BO_000000041_01:
'Información sobre el Interés que Pagan las Empresas por Sus Préstamos
con Entidades Financieras'.
"""

import os
import re
import traceback
import numpy as np
import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000041_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000041_01:
    'Información sobre el Interés que Pagan las Empresas por Sus Préstamos
    con Entidades Financieras'.
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
        Extracts loan interest rates data from Excel, normalizing the multi-level
        grid of financial institutions and economic sectors into vertical melted format.

        Parameters
        ----------
        file_path : str
            Absolute path to downloaded Excel file.
        key_words : str
            Keywords for identification (if applicable).
        template_path : str
            Path to reference template (if applicable).
        page_number : int
            Page / sheet index (defaults to 1).
        format : str
            Target date format (defaults to '%Y-%m-%d').

        Returns
        -------
        tuple
            Tuple of (metadata_dict, df_melted).
        """
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet_names = wb.sheetnames
            sheet_idx = max(0, min(int(page_number) - 1, len(sheet_names) - 1))
            ws = wb[sheet_names[sheet_idx]]

            # 1. Extract report titles from top header rows
            titles = []
            for r in range(1, 6):
                val = ws.cell(r, 1).value
                if val and isinstance(val, str) and val.strip():
                    titles.append(val.strip())

            # 2. Extract cutoff date dynamically from header or file name
            date_str = None
            spanish_months = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'setiembre': 9, 'octubre': 10,
                'noviembre': 11, 'diciembre': 12
            }

            for t in titles:
                match = re.search(
                    r'al\s+(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})',
                    t,
                    re.IGNORECASE
                )
                if match:
                    day = int(match.group(1))
                    month_name = match.group(2).lower()
                    year = int(match.group(3))
                    month = spanish_months.get(month_name)
                    if month:
                        date_str = f"{year:04d}-{month:02d}-{day:02d}"
                        break

            if not date_str:
                file_name = os.path.basename(file_path)
                match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
                if match:
                    date_str = match.group(1)

            # 3. Locate anchor cell 'Entidades' using strict regex
            anchor_row = None
            for r in range(1, 15):
                c1_val = ws.cell(r, 1).value
                if c1_val and re.match(
                    r"^entidades$", str(c1_val).strip(), re.IGNORECASE
                ):
                    anchor_row = r
                    break

            if anchor_row is None:
                raise ValueError("Could not find anchor header 'Entidades' in sheet.")

            # 4. Map columns: nv3 (Sector) and nv4 (Company size)
            col_nv3 = {}
            col_nv4 = {}
            current_category = None

            for c in range(2, ws.max_column + 1):
                top_val = ws.cell(anchor_row, c).value
                sub_val = ws.cell(anchor_row + 1, c).value

                if top_val and str(top_val).strip():
                    current_category = str(top_val).strip()

                if sub_val and str(sub_val).strip():
                    col_nv3[c] = current_category
                    col_nv4[c] = str(sub_val).strip()

            # 5. Extract rows using state machine
            records = []
            anchor_val = ws.cell(anchor_row, 1).value
            current_nv1 = str(anchor_val).strip() if anchor_val else "Entidades"

            for r in range(anchor_row + 2, ws.max_row + 1):
                c1_cell = ws.cell(r, 1)
                c1_val = c1_cell.value
                if not c1_val or not str(c1_val).strip():
                    continue

                text = str(c1_val).strip()

                # Skip footnote and metadata lines
                if re.match(r"^(fuente|\*|nota)\b", text, re.IGNORECASE):
                    continue

                # Skip summary total rows to prevent double counting
                if re.match(r"^total\b", text, re.IGNORECASE):
                    continue

                row_vals = {c: ws.cell(r, c).value for c in col_nv3}

                # If no numeric data in columns, update category state
                is_header = not any(
                    isinstance(v, (int, float)) for v in row_vals.values()
                )

                if is_header:
                    current_nv1 = text
                    continue

                # Record non-empty numeric data points
                for c, val in row_vals.items():
                    if val is None or val == "":
                        continue
                    records.append({
                        'nv1': current_nv1,
                        'nv2': text,
                        'nv3': col_nv3[c],
                        'nv4': col_nv4[c],
                        'fecha': date_str,
                        'valor': val
                    })

            df_melted = pd.DataFrame(records)
            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number)
            }

            if df_melted.empty:
                return (
                    metadata_dict,
                    pd.DataFrame(columns=['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor'])
                )

            # 6. Format numeric values: round to 6 decimal places
            df_melted['valor'] = pd.to_numeric(
                df_melted['valor'], errors='coerce'
            ).round(6)
            df_melted = df_melted.dropna(subset=['valor'])
            df_melted['valor'] = df_melted['valor'].apply(
                lambda x: np.format_float_positional(x, trim='-') if pd.notna(x) else x
            )

            # Ensure all level and date columns are strings
            for col in ['nv1', 'nv2', 'nv3', 'nv4', 'fecha']:
                df_melted[col] = df_melted[col].astype(str)

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
        Validates structural and numeric consistency of extracted interest rates.
        Since interest rates are non-additive, this verifies numeric integrity.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Extracted DataFrame with metadata columns.
        decimal_separator : str
            Configured decimal separator ('.' or ',').
        TOLERANCE : float
            Allowable numerical tolerance (defaults to 6.0).

        Returns
        -------
        bool
            False if validation succeeds, True if errors or discrepancies are detected.
        """
        try:
            if dataframe.empty or 'valor' not in dataframe.columns:
                return False

            vals = pd.to_numeric(dataframe['valor'], errors='coerce')
            if vals.isna().all():
                return True

            # Interest rates must be non-negative
            if (vals < 0).any():
                return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000041_01 = D_BO_000000041_01
Robot = D_BO_000000041_01
