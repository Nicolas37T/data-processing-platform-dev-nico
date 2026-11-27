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

class D_BO_000000102_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000102_01:
    'Base Monetaria, Determinantes y Componentes'.
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
        Extracts monetary base determinants and components from an Excel file,
        normalizing time series data into a vertical melted structure.

        Parameters
        ----------
        file_path : str
            Path to the downloaded Excel file.
        key_words : str
            Keywords to identify the target report (optional).
        template_path : str
            Path to template file (optional).
        page_number : int
            Page / sheet index (defaults to 1).
        format : str
            Target date format (defaults to '%Y-%m-%d').

        Returns
        -------
        tuple
            (metadata_dict, df_melted) where metadata_dict contains report
            metadata and df_melted contains [nv1, nv2, nv3, fecha, valor].
        """
        try:
            sheet_idx = page_number - 1 if page_number and page_number > 0 else 0
            df_raw = pd.read_excel(file_path, sheet_name=sheet_idx, header=None)

            # 1. Extract titles from header rows (rows 0 to 3)
            titles = []
            for r_idx in range(4):
                val = df_raw.iloc[r_idx, 0]
                if pd.notna(val):
                    clean_t = re.sub(r'\s+', ' ', str(val)).strip()
                    if clean_t:
                        titles.append(clean_t)

            if not titles:
                titles = [
                    "BASE MONETARIA, DETERMINANTES Y COMPONENTES",
                    "(En miles de bolivianos)"
                ]

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number)
            }

            # 2. Map date columns from row 4
            spanish_months = {
                'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12
            }

            date_row = 4
            col_date_mapping = {}
            for col_idx in range(1, df_raw.shape[1]):
                cell_val = df_raw.iloc[date_row, col_idx]
                if pd.isna(cell_val):
                    continue

                parsed_date = None
                if isinstance(cell_val, (datetime.datetime, pd.Timestamp)):
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

            # 3. State machine to capture hierarchy
            records = []
            current_nv1 = None
            current_nv2 = None
            current_nv3 = None

            for row_idx in range(5, df_raw.shape[0]):
                raw_label = df_raw.iloc[row_idx, 0]
                if pd.isna(raw_label):
                    if current_nv1 == "COMPONENTES" and current_nv2 == "Reservas Bancarias":
                        break
                    continue

                label_str = str(raw_label)
                clean_label = re.sub(r'\s+', ' ', label_str).strip()
                if not clean_label:
                    continue

                # Stop conditions: currency breakdown or memo items
                clean_upper = clean_label.upper()
                if clean_upper in ["MONEDA NACIONAL", "ITEMS PRO MEMORIA"]:
                    break

                leading_spaces = len(label_str) - len(label_str.lstrip(' '))

                # Root level (nv1)
                if re.match(r"^DETERMINANTES$", clean_label, re.IGNORECASE):
                    current_nv1 = "DETERMINANTES"
                    current_nv2 = None
                    current_nv3 = None
                elif re.match(r"^COMPONENTES$", clean_label, re.IGNORECASE):
                    current_nv1 = "COMPONENTES"
                    current_nv2 = None
                    current_nv3 = None
                elif current_nv1 == "DETERMINANTES":
                    if re.match(r"^OMA\b", clean_label, re.IGNORECASE):
                        current_nv2 = clean_label
                        current_nv3 = None
                    elif current_nv2 and (re.search(r"MN\s*\+\s*UFV", clean_label, re.I) or
                                          re.search(r"ME\s*\+\s*CMV", clean_label, re.I)):
                        current_nv3 = clean_label
                    else:
                        current_nv2 = clean_label
                        current_nv3 = None
                elif current_nv1 == "COMPONENTES":
                    if re.match(r"^Billetes\s+y\s+Monedas$", clean_label, re.IGNORECASE):
                        current_nv2 = clean_label
                        current_nv3 = None
                    elif re.match(r"^Reservas\s+Bancarias$", clean_label, re.IGNORECASE):
                        current_nv2 = clean_label
                        current_nv3 = None
                    elif current_nv2 == "Reservas Bancarias" and leading_spaces >= 2:
                        current_nv3 = clean_label

                # Extract data for mapped columns
                for col_idx, date_str in col_date_mapping.items():
                    val = df_raw.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        try:
                            num_val = float(val)
                            records.append({
                                'nv1': current_nv1,
                                'nv2': current_nv2,
                                'nv3': current_nv3,
                                'fecha': date_str,
                                'valor': num_val
                            })
                        except (ValueError, TypeError):
                            pass

            df_melted = pd.DataFrame(records)
            if df_melted.empty:
                return metadata_dict, pd.DataFrame(
                    columns=['nv1', 'nv2', 'nv3', 'fecha', 'valor']
                )

            # Round to nearest integer and format to prevent scientific notation
            df_melted['valor'] = df_melted['valor'].apply(
                lambda x: np.format_float_positional(float(round(x)), trim='-') if pd.notna(x) else x
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
        Validates the mathematical and accounting integrity of the extracted
        monetary base report.

        Accounting relations verified per date:
        1. DETERMINANTES == RIN + CredPub + CredBan - OMA 1 + ResMon + Otras Cuentas
        2. OMA 1 == (MN + UFV) + (ME + CMV)
        3. COMPONENTES == Billetes y Monedas + Reservas Bancarias
        4. Reservas Bancarias == Depósitos Corrientes + Encaje Legal + Otros + Caja
        5. DETERMINANTES == COMPONENTES

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

            # Convert 'valor' to numeric
            try:
                df_check['valor_num'] = to_numeric_datax(df_check['valor'], decimal_separator)
            except Exception:
                import traceback; traceback.print_exc()
                df_check['valor_num'] = pd.to_numeric(df_check['valor'], errors='coerce')

            if df_check['valor_num'].isna().any():
                df_check['valor_num'] = pd.to_numeric(df_check['valor'], errors='coerce')

            unique_dates = df_check['fecha'].dropna().unique()

            for target_date in unique_dates:
                df_date = df_check[df_check['fecha'] == target_date]

                def get_metric(nv1_val, nv2_pattern=None, nv3_pattern=None, is_nv3_none=False):
                    mask = (df_date['nv1'] == nv1_val)
                    if nv2_pattern is not None:
                        mask &= df_date['nv2'].astype(str).str.contains(nv2_pattern, case=False, regex=True, na=False)
                    elif nv2_pattern is None and nv3_pattern is None and is_nv3_none:
                        mask &= df_date['nv2'].isna()

                    if nv3_pattern is not None:
                        mask &= df_date['nv3'].astype(str).str.contains(nv3_pattern, case=False, regex=True, na=False)
                    elif is_nv3_none:
                        mask &= df_date['nv3'].isna()

                    matched = df_date.loc[mask, 'valor_num']
                    return matched.iloc[0] if not matched.empty else None

                det = get_metric("DETERMINANTES", is_nv3_none=True)
                rin = get_metric("DETERMINANTES", nv2_pattern=r"Reservas\s+Internacionales\s+Netas", is_nv3_none=True)
                cred_pub = get_metric("DETERMINANTES", nv2_pattern=r"Cr[eé]dito\s+Neto\s+al\s+Sector\s+P[uú]blico", is_nv3_none=True)
                cred_ban = get_metric("DETERMINANTES", nv2_pattern=r"Cr[eé]dito\s+a\s+Bancos", is_nv3_none=True)
                oma = get_metric("DETERMINANTES", nv2_pattern=r"^OMA", is_nv3_none=True)
                oma_mn = get_metric("DETERMINANTES", nv2_pattern=r"^OMA", nv3_pattern=r"MN\s*\+\s*UFV")
                oma_me = get_metric("DETERMINANTES", nv2_pattern=r"^OMA", nv3_pattern=r"ME\s*\+\s*CMV")
                res_mon = get_metric("DETERMINANTES", nv2_pattern=r"Reserva\s+Monetaria", is_nv3_none=True)
                otras = get_metric("DETERMINANTES", nv2_pattern=r"Otras\s+Cuentas", is_nv3_none=True)

                comp = get_metric("COMPONENTES", is_nv3_none=True)
                billetes = get_metric("COMPONENTES", nv2_pattern=r"Billetes\s+y\s+Monedas", is_nv3_none=True)
                res_ban = get_metric("COMPONENTES", nv2_pattern=r"Reservas\s+Bancarias", is_nv3_none=True)
                dep_corr = get_metric("COMPONENTES", nv2_pattern=r"Reservas\s+Bancarias", nv3_pattern=r"Dep[oó]sitos\s+Corrientes")
                encaje = get_metric("COMPONENTES", nv2_pattern=r"Reservas\s+Bancarias", nv3_pattern=r"Encaje\s+Legal")
                otros = get_metric("COMPONENTES", nv2_pattern=r"Reservas\s+Bancarias", nv3_pattern=r"Otros")
                caja = get_metric("COMPONENTES", nv2_pattern=r"Reservas\s+Bancarias", nv3_pattern=r"Caja")

                # 1. Determinantes Total Check
                if all(v is not None for v in [det, rin, cred_pub, cred_ban, oma, otras]):
                    res_mon_val = res_mon if res_mon is not None else 0.0
                    det_calc = rin + cred_pub + cred_ban - oma + res_mon_val + otras
                    if abs(det - det_calc) > TOLERANCE:
                        print(f"Validation Error [DETERMINANTES] on {target_date}: extracted={det}, calculated={det_calc}")
                        return True

                # 2. OMA Breakdown Check
                if all(v is not None for v in [oma, oma_mn, oma_me]):
                    oma_calc = oma_mn + oma_me
                    if abs(oma - oma_calc) > TOLERANCE:
                        print(f"Validation Error [OMA] on {target_date}: extracted={oma}, calculated={oma_calc}")
                        return True

                # 3. Componentes Total Check
                if all(v is not None for v in [comp, billetes, res_ban]):
                    comp_calc = billetes + res_ban
                    if abs(comp - comp_calc) > TOLERANCE:
                        print(f"Validation Error [COMPONENTES] on {target_date}: extracted={comp}, calculated={comp_calc}")
                        return True

                # 4. Reservas Bancarias Breakdown Check
                if all(v is not None for v in [res_ban, dep_corr, encaje, otros, caja]):
                    res_ban_calc = dep_corr + encaje + otros + caja
                    if abs(res_ban - res_ban_calc) > TOLERANCE:
                        print(f"Validation Error [Reservas Bancarias] on {target_date}: extracted={res_ban}, calculated={res_ban_calc}")
                        return True

                # 5. Parity between Determinantes and Componentes
                if det is not None and comp is not None:
                    if abs(det - comp) > TOLERANCE:
                        print(f"Validation Error [DET vs COMP] on {target_date}: det={det}, comp={comp}")
                        return True

            return False

        except Exception as error:
            print(f"Validation exception occurred: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000102_01 = D_BO_000000102_01
Robot = D_BO_000000102_01
