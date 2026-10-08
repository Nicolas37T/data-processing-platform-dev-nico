from models.conversion.Conversion_Base import Conversion_Base
"""
Module for extracting and validating report D_BO_000000320_01.

Report Code: D_BO_000000320_01
Report Name: Bmu-ponderación de Activos y Suficiencia Patrimonial
Periodicity: Mensual
Page: 1
Decimal Separator: ,
Conversion Factor: 1
Keywords: bmu cap
"""

import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import xlrd
from unidecode import unidecode

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000320_01(Conversion_Base):
    """Conversion robot for report D_BO_000000320_01."""

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

            # Percentage formatting (e.g. 0.1307 -> 13.07)
            if "%" in num_fmt:
                return num * 100.0

            # Preserve exact numeric float value as requested by DATAX specifications
            return num

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

            # 1. Parse report reference date dynamically
            report_date = parse_report_date(sheet, os.path.basename(file_path))

            # 2. Locate header columns across all bank entities dynamically
            header_row_idx = -1
            col_entities: Dict[int, str] = {}
            for r_idx in range(min(sheet.nrows, 10)):
                found_entities: Dict[int, str] = {}
                for c_idx in range(1, sheet.ncols):
                    c_txt = re.sub(r"\s+", " ", str(sheet.cell_value(r_idx, c_idx) or "")).strip()
                    if c_txt:
                        found_entities[c_idx] = c_txt
                # The entity header row contains multiple bank codes (e.g. BNB, BUN, etc.)
                if len(found_entities) >= 2:
                    col_entities = found_entities
                    header_row_idx = r_idx
                    break

            if header_row_idx == -1 or not col_entities:
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
                    "BANCOS MULTIPLES",
                    "PONDERACIÓN DE ACTIVOS Y SUFICIENCIA PATRIMONIAL",
                    f"AL {report_date}",
                    "(en bolivianos)",
                ]

            # 4. Map rows to taxonomic levels (nv1, nv2, nv3) using structural indentation
            rows_list: List[Dict[str, Any]] = []
            current_parent_section: Optional[str] = None

            for r_idx in range(header_row_idx + 1, sheet.nrows):
                raw_label = str(sheet.cell_value(r_idx, 0) or "")
                cleaned_label = re.sub(r"\s+", " ", raw_label).strip()

                if not cleaned_label or cleaned_label.startswith("(1)"):
                    break

                norm_label = unidecode(cleaned_label).upper()
                
                # Detectar sangría por espacios en blanco, tabs o formato de celda en Excel
                xf_indent = 0
                try:
                    xf = book.xf_list[sheet.cell(r_idx, 0).xf_index]
                    xf_indent = xf.alignment.indent_level
                except Exception:
                    pass

                has_leading_spaces = (len(raw_label) - len(raw_label.lstrip())) >= 2 or "\t" in raw_label
                is_indented = has_leading_spaces or xf_indent > 0

                # Clasificación explícita de subcuentas conocidas de Capital Primario
                is_sub_primario = (
                    norm_label == "OTROS AJUSTES"
                    or "DEFICIT DE PREVISIONES" in norm_label
                    or "DEFICIT DE PROVISIONES" in norm_label
                )
                # Clasificación explícita de subcuentas conocidas de Obligaciones Subordinadas
                is_sub_subordinadas = (
                    "OBLIGACIONES SUBORDINADAS" in norm_label
                    and "COMPUTABLES" not in norm_label
                )

                nv1: Optional[str] = None
                nv2: Optional[str] = None
                nv3: Optional[str] = None

                if is_sub_primario:
                    nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                    nv2 = current_parent_section or "CAPITAL PRIMARIO INICIAL"
                    nv3 = cleaned_label
                elif is_sub_subordinadas:
                    nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                    nv2 = current_parent_section or "OBLIGACIONES SUBORDINADAS COMPUTABLES (1)"
                    nv3 = cleaned_label
                elif is_indented and current_parent_section is not None:
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
                    elif norm_label == "CAPITAL REGULATORIO":
                        current_parent_section = "CAPITAL REGULATORIO"
                        nv1 = "CAPITAL REGULATORIO"
                    elif "EXCEDENTE" in norm_label and "DEFICIT" in norm_label:
                        nv1 = "CAPITAL REGULATORIO"
                        nv2 = cleaned_label
                    elif norm_label.startswith("COEFICIENTE DE INVERSION EN ACTIVOS FIJOS"):
                        nv1 = "CAPITAL REGULATORIO"
                        nv2 = cleaned_label
                    elif current_parent_section is not None:
                        # Elemento hijo bajo la sección padre activa
                        nv1 = "CAPITAL PRIMARIO DESPUÉS DE AJUSTES"
                        nv2 = current_parent_section
                        nv3 = cleaned_label
                    else:
                        current_parent_section = None
                        nv1 = cleaned_label

                # Extract values across all entity columns
                for col_idx, entity_name in col_entities.items():
                    cell_obj = sheet.cell(r_idx, col_idx)
                    num_fmt_str = ""
                    try:
                        xf_index = cell_obj.xf_index
                        xf = book.xf_list[xf_index]
                        fmt_key = xf.format_key
                        fmt = book.format_map.get(fmt_key)
                        num_fmt_str = fmt.format_str if fmt else ""
                    except Exception:
                        import traceback; traceback.print_exc()
                        num_fmt_str = ""

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

                # 2. Reconcile Capital Primario: Inicial - Sum(Deducciones) == Total Primario
                cp_ini_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"] == "CAPITAL PRIMARIO INICIAL")
                    & (edf["nv3"].isna())
                ]
                cp_deductions_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"] == "CAPITAL PRIMARIO INICIAL")
                    & (edf["nv3"].notna())
                ]
                cp_tot_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].isna())
                ]
                if not cp_ini_rows.empty and not cp_tot_rows.empty:
                    cp_ini = cp_ini_rows["valor"].iloc[0]
                    cp_ded = cp_deductions_rows["valor"].sum() if not cp_deductions_rows.empty else 0.0
                    cp_tot = cp_tot_rows["valor"].iloc[0]
                    calc_cp = cp_ini - cp_ded
                    diff_cp = abs(calc_cp - cp_tot)
                    if diff_cp > TOLERANCE:
                        print(
                            f"Validation error in Capital Primario ({entity}): "
                            f"calc={calc_cp}, total={cp_tot}, diff={diff_cp} > {TOLERANCE}"
                        )
                        return True

                # 3. Reconcile Capital Secundario: Previsiones + Obligaciones Subordinadas == Total Secundario
                cs_prev_rows = edf[
                    (edf["nv1"] == "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].str.contains("PREVISIONES", na=False))
                ]
                cs_sub_rows = edf[
                    (edf["nv1"] == "CAPITAL PRIMARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].str.contains("OBLIGACIONES SUBORDINADAS", na=False))
                    & (edf["nv3"].isna())
                ]
                cs_tot_rows = edf[
                    (edf["nv1"] == "CAPITAL SECUNDARIO DESPUÉS DE AJUSTES")
                    & (edf["nv2"].isna())
                ]
                if not cs_prev_rows.empty and not cs_tot_rows.empty:
                    cs_prev = cs_prev_rows["valor"].iloc[0]
                    cs_sub = cs_sub_rows["valor"].iloc[0] if not cs_sub_rows.empty else 0.0
                    cs_tot = cs_tot_rows["valor"].iloc[0]
                    calc_cs = cs_prev + cs_sub
                    diff_cs = abs(calc_cs - cs_tot)
                    if diff_cs > TOLERANCE:
                        print(
                            f"Validation error in Capital Secundario ({entity}): "
                            f"calc={calc_cs}, total={cs_tot}, diff={diff_cs} > {TOLERANCE}"
                        )
                        return True

                # 4. Reconcile Capital Regulatorio: Primario + Secundario - Inversiones == Regulatorio
                cap_reg_rows = edf[
                    (edf["nv1"] == "CAPITAL REGULATORIO") & (edf["nv2"].isna())
                ]
                inv_rows = edf[
                    edf["nv1"].str.startswith("INVERSIONES", na=False)
                ]
                if not cp_tot_rows.empty and not cs_tot_rows.empty and not cap_reg_rows.empty:
                    cp_val = cp_tot_rows["valor"].iloc[0]
                    cs_val = cs_tot_rows["valor"].iloc[0]
                    inv_val = inv_rows["valor"].sum() if not inv_rows.empty else 0.0
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
                exc_rows = edf[
                    (edf["nv1"] == "CAPITAL REGULATORIO")
                    & (edf["nv2"].str.contains("EXCEDENTE", na=False))
                ]
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

Executor_D_BO_000000320_01 = D_BO_000000320_01
Robot = D_BO_000000320_01
