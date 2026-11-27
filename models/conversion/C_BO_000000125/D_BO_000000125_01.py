from models.conversion.Conversion_Base import Conversion_Base
"""
Conversion robot for report D_BO_000000125_01:
'Financiamiento Concedido por el Sistema Bancario al Sector Privado
y Empresas con Participación Pública P'.
"""
import calendar
import datetime
import os
import re
import traceback
import numpy as np
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000125_01(Conversion_Base):
    """
    Conversion robot class for extracting bank financing by economic sector
    into a standardized melted DataFrame.
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
        Extracts financing data from Excel and transforms it into a melted format.

        Parameters
        ----------
        file_path : str
            Absolute path to the downloaded Excel file.
        key_words : str
            Keywords to identify target table (optional).
        template_path : str
            Path to reference template (optional).
        page_number : int
            Sheet page number (1-based index, defaults to 1).
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

            # 1. Dynamically extract header titles from the top rows
            titles = []
            for r_idx in range(min(5, df_raw.shape[0])):
                val = df_raw.iloc[r_idx, 0]
                if pd.notna(val):
                    clean_title = re.sub(r'\s+', ' ', str(val)).strip()
                    if clean_title:
                        titles.append(clean_title)

            # 2. Dynamically extract the reporting cutoff date
            spanish_months = {
                'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
                'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
                'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10,
                'NOVIEMBRE': 11, 'DICIEMBRE': 12
            }
            cutoff_date = None
            for title in titles:
                match = re.search(r'\b([A-Z]+)\s+DE\s+(\d{4})\b', title.upper())
                if match:
                    month_name, year_str = match.group(1), match.group(2)
                    if month_name in spanish_months:
                        year = int(year_str)
                        month = spanish_months[month_name]
                        _, last_day = calendar.monthrange(year, month)
                        cutoff_date = f"{year:04d}-{month:02d}-{last_day:02d}"
                        break

            if not cutoff_date:
                file_match = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(file_path))
                if file_match:
                    cutoff_date = file_match.group(1)
                else:
                    cutoff_date = datetime.date.today().strftime("%Y-%m-%d")

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number) if page_number and int(page_number) > 0 else 1
            }

            # 3. Locate anchor row in column 0 (e.g., 'BANCOS')
            anchor_row = None
            for r in range(min(15, df_raw.shape[0])):
                cell_val = df_raw.iloc[r, 0]
                if pd.notna(cell_val) and re.match(r'^BANCOS$', str(cell_val).strip(), re.IGNORECASE):
                    anchor_row = r
                    break

            if anchor_row is None:
                anchor_row = 6

            nv1_root = str(df_raw.iloc[anchor_row, 0]).strip().capitalize()

            # 4. Construct multi-line column headers for columns 1 to N
            col_headers = {}
            for col_idx in range(1, df_raw.shape[1]):
                header_parts = []
                for scan_row in range(max(0, anchor_row - 2), min(anchor_row + 2, df_raw.shape[0])):
                    val = df_raw.iloc[scan_row, col_idx]
                    if pd.notna(val):
                        val_str = str(val).strip()
                        if val_str:
                            header_parts.append(val_str)
                combined_header = " ".join(header_parts)
                combined_header = re.sub(r'\s+', ' ', combined_header).strip()
                if combined_header:
                    col_headers[col_idx] = combined_header

            # 5. State machine to process categories and entities without hardcoding
            records = []
            current_nv2 = None
            current_nv3 = None

            for row_idx in range(anchor_row + 1, df_raw.shape[0]):
                c0 = df_raw.iloc[row_idx, 0]
                c0_clean = re.sub(r'\s+', ' ', str(c0)).strip() if pd.notna(c0) else ""
                c0_upper = c0_clean.upper()

                # Stop reading at footnotes or source attribution
                if any(c0_upper.startswith(k) for k in ["FUENTE", "ELABORACIÓN", "ELABORACION", "NOTA"]):
                    break

                # Count numeric occurrences across mapped columns
                numeric_cells = sum(
                    pd.notna(df_raw.iloc[row_idx, c]) and isinstance(df_raw.iloc[row_idx, c], (int, float))
                    for c in col_headers
                )
                has_numeric = (numeric_cells > 0)

                # Skip blank separator rows
                if not c0_clean and not has_numeric:
                    continue

                # Skip aggregate rows to prevent double counting
                if c0_upper.startswith("TOTAL") or c0_upper.startswith("FINANCIAMIENTO"):
                    current_nv2 = None
                    current_nv3 = None
                    continue

                # Header rows define parent categories (nv2)
                if not has_numeric:
                    current_nv2 = c0_clean
                    current_nv3 = None
                    continue

                # Data rows define entities
                if current_nv2 is not None:
                    row_nv2 = current_nv2
                    row_nv3 = c0_clean
                else:
                    row_nv2 = c0_clean
                    row_nv3 = None

                # Extract metric values across all column sectors
                for col_idx, header_name in col_headers.items():
                    val = df_raw.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        try:
                            num_val = float(val)
                            records.append({
                                'nv1': nv1_root,
                                'nv2': row_nv2,
                                'nv3': row_nv3,
                                'nv4': header_name,
                                'fecha': cutoff_date,
                                'valor': num_val
                            })
                        except (ValueError, TypeError):
                            pass

            df_melted = pd.DataFrame(records)
            if df_melted.empty:
                return metadata_dict, pd.DataFrame(
                    columns=['nv1', 'nv2', 'nv3', 'nv4', 'fecha', 'valor']
                )

            # Prevent scientific notation and remove empty rows
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
        Validates mathematical consistency of extracted figures.
        Reconciles the horizontal sum of economic sectors against the SUBTOTAL
        column for each banking entity.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Extracted melted DataFrame.
        decimal_separator : str
            Decimal separator character ('.' or ',').
        TOLERANCE : float
            Allowed difference threshold due to rounding (default: 6.0).

        Returns
        -------
        bool
            False if validation succeeds (no errors), True if discrepancy found.
        """
        try:
            if dataframe.empty or 'valor' not in dataframe.columns:
                return False

            df_check = dataframe.copy()
            df_check['valor_num'] = pd.to_numeric(df_check['valor'], errors='coerce')
            if df_check['valor_num'].isna().all():
                try:
                    df_check['valor_num'] = to_numeric_datax(df_check['valor'], decimal_separator)
                except Exception:
                    import traceback; traceback.print_exc()
                    pass

            # Exclude non-sector columns from the sector sum
            sectors_df = df_check[~df_check['nv4'].isin(['SUBTOTAL', 'Particip. %'])]
            subtotals_df = df_check[df_check['nv4'] == 'SUBTOTAL']

            if sectors_df.empty or subtotals_df.empty:
                return False

            grouped = (
                sectors_df.groupby(['nv1', 'nv2', 'nv3', 'fecha'], dropna=False)['valor_num']
                .sum()
                .reset_index()
            )
            grouped.rename(columns={'valor_num': 'calculated_subtotal'}, inplace=True)

            merged = pd.merge(
                subtotals_df,
                grouped,
                on=['nv1', 'nv2', 'nv3', 'fecha']
            )

            discrepancy = (merged['valor_num'] - merged['calculated_subtotal']).abs()
            if (discrepancy > TOLERANCE).any():
                max_err = discrepancy.max()
                print(f"Validation failed: Horizontal sector sum discrepancy exceeds tolerance ({max_err} > {TOLERANCE})")
                return True

            return False

        except Exception as error:
            print(f"Error during validation: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000125_01 = D_BO_000000125_01
Robot = D_BO_000000125_01
