from models.conversion.Conversion_Base import Conversion_Base
"""
Module for extracting and validating report D_BO_000000319_01.

Report Code: D_BO_000000319_01
Report Name: Bdp-ponderación de Activos y Suficiencia Patrimonial
Periodicity: Mensual
Page: 1
Decimal Separator: ,
Conversion Factor: 1
"""

import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import xlrd
from unidecode import unidecode

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000319_01(Conversion_Base):
    """Conversion robot for report D_BO_000000319_01."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Extract asset risk-weighting and capital adequacy data from Excel source.

        Parameters
        ----------
        file_path : str
            Absolute path to downloaded source file (.xls or .xlsx).
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
        def parse_report_date(sheet_obj: Any, file_name_str: str) -> str:
            """Extract report date dynamically from sheet title or file name."""
            spanish_months = {
                "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
                "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
                "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
            }
            # 1. Search text in first 6 rows of sheet
            for r_idx in range(min(sheet_obj.nrows, 6)):
                val_txt = str(sheet_obj.cell_value(r_idx, 0) or "").strip().upper()
                date_match = re.search(
                    r"AL\s+(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})", val_txt
                )
                if date_match:
                    day = int(date_match.group(1))
                    month_str = unidecode(date_match.group(2))
                    year = int(date_match.group(3))
                    if month_str in spanish_months:
                        month_num = spanish_months[month_str]
                        return f"{year:04d}-{month_num:02d}-{day:02d}"

            # 2. Extract from file name (e.g. 202607_...)
            fn_ym = re.search(r"(\d{4})(\d{2})", file_name_str)
            if fn_ym:
                y = int(fn_ym.group(1))
                m = int(fn_ym.group(2))
                end_of_month = pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0)
                return end_of_month.strftime(format)

            return (pd.Timestamp.now() - pd.offsets.MonthEnd(1)).strftime(format)

        def clean_numeric_value(cell_val: Any, num_fmt: str) -> Optional[float]:
            """Parse and format cell numeric value according to its display format."""
            if cell_val is None or cell_val == "":
                return None
            try:
                num = float(cell_val)
            except (ValueError, TypeError):
                return None

            # Percentage formatting (e.g. 0.00% -> 16.27)
            if "%" in num_fmt:
                return round(num * 100.0, 2)

            # Ratio formatting (e.g. 0.00 -> 0.32)
            if "0.00" in num_fmt:
                return round(num, 2)

            # Integer / currency amount formatting (e.g. #,##0 -> 67162.0)
            return float(round(num))

        try:
            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return "", pd.DataFrame()

            # Load workbook using xlrd (supporting formatting_info for XLS)
            try:
                book = xlrd.open_workbook(file_path, formatting_info=True)
            except Exception:
                import traceback; traceback.print_exc()
                book = xlrd.open_workbook(file_path)

            if book.nsheets == 0:
                print(f"No sheets found in {file_path}")
                return "", pd.DataFrame()

            sheet_idx = page_number - 1 if page_number <= book.nsheets else 0
            sheet = book.sheet_by_index(sheet_idx)

            # 1. Parse report reference date
            report_date = parse_report_date(sheet, os.path.basename(file_path))

            # 2. Locate header columns (BDR and TOTAL SISTEMA)
            header_row_idx = -1
            col_entities: Dict[int, str] = {}
            for r_idx in range(min(sheet.nrows, 10)):
                for c_idx in range(sheet.ncols):
                    c_txt = unidecode(str(sheet.cell_value(r_idx, c_idx) or "")).strip().upper()
                    if c_txt == "BDR":
                        col_entities[c_idx] = "BDR"
                        header_row_idx = r_idx
                    elif "TOTAL SISTEMA" in c_txt:
                        col_entities[c_idx] = "TOTAL SISTEMA"
                        header_row_idx = r_idx

            if header_row_idx == -1 or len(col_entities) < 2:
                print(f"Could not locate entity columns in {file_path}")
                return "", pd.DataFrame()

            # 3. Extract metadata titles from top rows
            titles_list: List[str] = []
            for r_idx in range(header_row_idx):
                t_val = str(sheet.cell_value(r_idx, 0) or "").strip()
                if t_val:
                    clean_t = re.sub(r"\s+", " ", t_val).strip()
                    if clean_t and clean_t not in titles_list:
                        titles_list.append(clean_t)

            if not titles_list:
                titles_list = [
                    "BANCOS DE DESARROLLO PRODUCTIVO",
                    "PONDERACIÓN DE ACTIVOS Y SUFICIENCIA PATRIMONIAL",
                    f"AL {report_date}",
                    "(en bolivianos)",
                ]

            # 4. Map rows to taxonomic levels (nv1, nv2, nv3)
            rows_list: List[Dict[str, Any]] = []
            current_parent_section: Optional[str] = None

            for r_idx in range(header_row_idx + 1, sheet.nrows):
                raw_label = str(sheet.cell_value(r_idx, 0) or "")
                cleaned_label = re.sub(r"\s+", " ", raw_label).strip()

                if not cleaned_label or cleaned_label.startswith("(1)"):
                    break

                norm_label = unidecode(cleaned_label).upper()
                is_indented = (len(raw_label) - len(raw_label.lstrip())) >= 4

                nv1: Optional[str] = None
                nv2: Optional[str] = None
                nv3: Optional[str] = None

                if is_indented:
                    nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                    nv2 = current_parent_section
                    nv3 = cleaned_label
                else:
                    if norm_label.startswith("CATEGORIA"):
                        nv1 = "TOTAL ACTIVO Y CONTINGENTE"
                        nv2 = cleaned_label
                    elif norm_label == "TOTAL ACTIVO Y CONTINGENTE":
                        nv1 = "TOTAL ACTIVO Y CONTINGENTE"
                    elif norm_label == "CAPITAL PRIMARIO INICIAL":
                        current_parent_section = cleaned_label
                        nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                        nv2 = cleaned_label
                    elif norm_label == "CAPITAL PRIMARIO DESPUES DE AJUSTES":
                        current_parent_section = None
                        nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                    elif "OBLIGACIONES SUBORDINADAS COMPUTABLES" in norm_label:
                        current_parent_section = cleaned_label
                        nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                        nv2 = cleaned_label
                    elif "PREVISIONES GENERICAS VOLUNTARIAS" in norm_label:
                        current_parent_section = None
                        nv1 = "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES"
                        nv2 = cleaned_label
                    elif "OTROS AJUSTES CAPITAL SECUNDARIO" in norm_label:
                        current_parent_section = None
                        nv1 = "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES"
                        nv2 = cleaned_label
                    elif norm_label == "CAPITAL SECUNDARIO DESPUES DE AJUSTES":
                        current_parent_section = None
                        nv1 = "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES"
                    else:
                        current_parent_section = None
                        nv1 = cleaned_label

                # Extract for each entity column
                for col_idx, entity_name in col_entities.items():
                    cell_obj = sheet.cell(r_idx, col_idx)
                    num_fmt_str = ""
                    try:
                        xf_obj = book.xf_list[cell_obj.xf_index]
                        fmt_entry = book.format_map.get(xf_obj.format_key)
                        if fmt_entry:
                            num_fmt_str = fmt_entry.format_str
                    except Exception:
                        import traceback; traceback.print_exc()
                        pass

                    numeric_val = clean_numeric_value(cell_obj.value, num_fmt_str)
                    if numeric_val is not None:
                        rows_list.append({
                            "nv1": nv1,
                            "nv2": nv2,
                            "nv3": nv3,
                            "nv4": entity_name,
                            "fecha": report_date,
                            "valor": numeric_val,
                        })

            if not rows_list:
                print(f"No numeric rows extracted from {file_path}")
                return "", pd.DataFrame()

            df_melted = pd.DataFrame(rows_list)

            # 5. Normalize valor column vectorized
            df_melted["valor"] = to_numeric_datax(
                serie=df_melted["valor"], decimal_separator=","
            )
            df_melted = df_melted.dropna(subset=["valor"])

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": titles_list,
                "page_number": page_number,
            }

            return (metadata, df_melted)

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
        """Validate consistency and arithmetic sums of extracted financial data.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Normalized DataFrame returned by extraction().
        decimal_separator : str, optional
            Decimal separator character (default ',').
        TOLERANCE : float, optional
            Maximum acceptable tolerance threshold for rounding differences (default 6.0).

        Returns
        -------
        bool
            False on success / valid, True on discrepancy or error.
        """
        try:
            if dataframe is None or not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True

            required_cols = ["nv1", "nv2", "nv3", "nv4", "fecha", "valor"]
            if not all(col in dataframe.columns for col in required_cols):
                return True

            df = dataframe.copy()
            df["valor"] = to_numeric_datax(df["valor"], decimal_separator=decimal_separator)
            if df["valor"].isna().any():
                return True

            for entity in df["nv4"].unique():
                edf = df[df["nv4"] == entity]

                # 1. Reconcile Total Activo y Contingente: Categories I to VI == Total
                cat_rows = edf[
                    (edf["nv1"] == "TOTAL ACTIVO Y CONTINGENTE") & (edf["nv2"].notna())
                ]
                tot_act_rows = edf[
                    (edf["nv1"] == "TOTAL ACTIVO Y CONTINGENTE") & (edf["nv2"].isna())
                ]
                if not cat_rows.empty and not tot_act_rows.empty:
                    cat_sum = cat_rows["valor"].sum()
                    tot_act = tot_act_rows["valor"].iloc[0]
                    diff_act = abs(cat_sum - tot_act)
                    if diff_act > TOLERANCE:
                        print(
                            f"Validation error in Activo ({entity}): "
                            f"sum={cat_sum}, total={tot_act}, diff={diff_act} > {TOLERANCE}"
                        )
                        return True

                # 2. Reconcile Capital Primario: Inicial - Otros Ajustes == Total Primario
                cp_ini_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"] == "CAPITAL PRIMARIO INICIAL")
                    & (edf["nv3"].isna())
                ]
                cp_ajustes_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"] == "CAPITAL PRIMARIO INICIAL")
                    & (edf["nv3"] == "Otros Ajustes")
                ]
                cp_tot_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].isna())
                ]
                if not cp_ini_rows.empty and not cp_tot_rows.empty:
                    cp_ini = cp_ini_rows["valor"].iloc[0]
                    cp_aj = cp_ajustes_rows["valor"].iloc[0] if not cp_ajustes_rows.empty else 0.0
                    cp_tot = cp_tot_rows["valor"].iloc[0]
                    calc_cp = cp_ini - cp_aj
                    diff_cp = abs(calc_cp - cp_tot)
                    if diff_cp > TOLERANCE:
                        print(
                            f"Validation error in Capital Primario ({entity}): "
                            f"calc={calc_cp}, total={cp_tot}, diff={diff_cp} > {TOLERANCE}"
                        )
                        return True

                # 3. Reconcile Capital Secundario: Previsiones == Total Secundario
                cs_prev_rows = edf[
                    (edf["nv1"] == "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"] == "PREVISIONES GENÉRICAS VOLUNTARIAS PARA PÉRDIDAS FUTURAS")
                ]
                cs_tot_rows = edf[
                    (edf["nv1"] == "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].isna())
                ]
                if not cs_prev_rows.empty and not cs_tot_rows.empty:
                    cs_prev = cs_prev_rows["valor"].iloc[0]
                    cs_tot = cs_tot_rows["valor"].iloc[0]
                    diff_cs = abs(cs_prev - cs_tot)
                    if diff_cs > TOLERANCE:
                        print(
                            f"Validation error in Capital Secundario ({entity}): "
                            f"prev={cs_prev}, total={cs_tot}, diff={diff_cs} > {TOLERANCE}"
                        )
                        return True

                # 4. Reconcile Capital Regulatorio: Primario + Secundario - Inversiones == Regulatorio
                cap_reg_rows = edf[edf["nv1"] == "CAPITAL REGULATORIO"]
                inv_otras_rows = edf[edf["nv1"] == "INVERSIONES EN OTRAS EMPRESAS NO CONSOLIDADAS"]
                if not cp_tot_rows.empty and not cs_tot_rows.empty and not cap_reg_rows.empty:
                    cp_val = cp_tot_rows["valor"].iloc[0]
                    cs_val = cs_tot_rows["valor"].iloc[0]
                    inv_val = inv_otras_rows["valor"].iloc[0] if not inv_otras_rows.empty else 0.0
                    reg_val = cap_reg_rows["valor"].iloc[0]
                    calc_reg = cp_val + cs_val - inv_val
                    diff_reg = abs(calc_reg - reg_val)
                    if diff_reg > TOLERANCE:
                        print(
                            f"Validation error in Capital Regulatorio ({entity}): "
                            f"calc={calc_reg}, actual={reg_val}, diff={diff_reg} > {TOLERANCE}"
                        )
                        return True

                # 5. Reconcile Excedente Patrimonial: Regulatorio - 10% Activo Computable == Excedente
                diez_pct_rows = edf[edf["nv1"] == "10% SOBRE ACTIVO COMPUTABLE"]
                exc_rows = edf[edf["nv1"] == "EXCEDENTE (DÉFICIT) PATRIMONIAL"]
                if not cap_reg_rows.empty and not diez_pct_rows.empty and not exc_rows.empty:
                    reg_val = cap_reg_rows["valor"].iloc[0]
                    diez_val = diez_pct_rows["valor"].iloc[0]
                    exc_val = exc_rows["valor"].iloc[0]
                    calc_exc = reg_val - diez_val
                    diff_exc = abs(calc_exc - exc_val)
                    if diff_exc > TOLERANCE:
                        print(
                            f"Validation error in Excedente ({entity}): "
                            f"calc={calc_exc}, actual={exc_val}, diff={diff_exc} > {TOLERANCE}"
                        )
                        return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Alias for compatibility with test runners expecting Robot

Executor_D_BO_000000319_01 = D_BO_000000319_01
Robot = D_BO_000000319_01
