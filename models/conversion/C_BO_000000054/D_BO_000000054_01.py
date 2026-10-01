from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import calendar
import unicodedata
import traceback
from typing import Tuple
import pandas as pd
import xlrd

from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000054_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000054_01:
    'Financial Statements by Entity - Clearing and Settlement Houses'
    Target sheet: '9300'
    """

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        try:
            file_name = os.path.basename(file_path)

            # 1. Resolve cutoff date dynamically from file name or header
            cut_date = None
            date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", file_name)
            if date_match:
                cut_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            else:
                date_ym = re.search(r"(\d{4})(\d{2})", file_name)
                if date_ym:
                    year, month = int(date_ym.group(1)), int(date_ym.group(2))
                    last_day = calendar.monthrange(year, month)[1]
                    cut_date = f"{year:04d}-{month:02d}-{last_day:02d}"

            # 2. Identify target sheet and load workbook
            with pd.ExcelFile(file_path) as excel_file:
                sheet_names = excel_file.sheet_names

            target_sheet = None
            if "9300" in sheet_names:
                target_sheet = "9300"
            elif key_words:
                for sheet in sheet_names:
                    if key_words.lower() in sheet.lower():
                        target_sheet = sheet
                        break
            if not target_sheet:
                idx = max(0, int(page_number) - 1)
                target_sheet = sheet_names[min(idx, len(sheet_names) - 1)]

            df_raw = pd.read_excel(file_path, sheet_name=target_sheet, header=None)

            # Fallback date resolution from header text if not found in filename
            if not cut_date:
                month_names = {
                    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
                    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
                }
                for r in range(min(5, len(df_raw))):
                    row_txt = str(df_raw.iloc[r, 0]).lower()
                    matched_date = re.search(r"al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", row_txt)
                    if matched_date:
                        day = int(matched_date.group(1))
                        month_num = month_names.get(matched_date.group(2), 1)
                        year = int(matched_date.group(3))
                        cut_date = f"{year:04d}-{month_num:02d}-{day:02d}"
                        break
                if not cut_date:
                    now = pd.Timestamp.now()
                    last_day = calendar.monthrange(now.year, now.month)[1]
                    cut_date = f"{now.year:04d}-{now.month:02d}-{last_day:02d}"

            # 3. Detect header row with entities and title rows
            header_row = 5
            for r in range(min(10, len(df_raw))):
                row_vals = [str(val).strip() for val in df_raw.iloc[r].dropna()]
                if any("TOTAL" in val for val in row_vals):
                    header_row = r
                    break

            titles = []
            for r in range(header_row):
                val = df_raw.iloc[r, 0]
                if pd.notna(val) and str(val).strip():
                    titles.append(str(val).strip())

            entities = {}
            for col_idx in range(1, df_raw.shape[1]):
                col_val = df_raw.iloc[header_row, col_idx]
                if pd.notna(col_val):
                    clean_ent = re.sub(r"\s+", " ", str(col_val)).strip()
                    entities[col_idx] = clean_ent

            # 4. Read indentation info from Excel sheet formatting
            cell_indents = {}
            try:
                wb_info = xlrd.open_workbook(file_path, formatting_info=True)
                xl_sheet = wb_info.sheet_by_name(target_sheet) if target_sheet in wb_info.sheet_names() else wb_info.sheet_by_index(0)
                for r in range(header_row + 1, min(len(df_raw), xl_sheet.nrows)):
                    xf = wb_info.xf_list[xl_sheet.cell_xf_index(r, 0)]
                    cell_indents[r] = xf.alignment.indent_level
            except Exception:
                import traceback; traceback.print_exc()
                cell_indents = {}

            # 5. Dynamic hierarchical parsing for Balance Sheet and Income Statement
            def normalize_text(text: str) -> str:
                if not text:
                    return ""
                return unicodedata.normalize("NFKD", str(text).strip()).encode("ASCII", "ignore").decode("utf-8").upper()

            balance_roots = {
                normalize_text("ACTIVO"): "ACTIVO",
                normalize_text("PASIVO"): "PASIVO",
                normalize_text("PATRIMONIO"): "PATRIMONIO",
                normalize_text("PASIVO Y PATRIMONIO"): "PASIVO Y PATRIMONIO",
                normalize_text("PASIVO + PATRIMONIO"): "PASIVO Y PATRIMONIO",
                normalize_text("CUENTAS CONTINGENTES DEUDORAS"): "CUENTAS CONTINGENTES DEUDORAS",
                normalize_text("CUENTAS DE ORDEN DEUDORAS"): "CUENTAS DE ORDEN DEUDORAS",
            }

            income_statement_blocks = [
                ("(=) RESULTADO FINANCIERO BRUTO", [
                    "(+) INGRESOS FINANCIEROS",
                    "(-) Gastos financieros",
                ]),
                ("(=) RESULTADO DE OPERACIÓN BRUTO", [
                    "(+) Otros ingresos operativos",
                    "(-) Otros gastos operativos",
                    "(+) Recuperaciones de activos financieros",
                    "(-) Cargos por incobrabilidad y desvalorización de activos financieros",
                    "RESULTADO DE OPERACIÓN  DESPUÉS DE INCOBRABLES",
                    "(-) Gastos de administración",
                    "RESULTADO DE OPERACIÓN NETO",
                    "(+)  Abonos por diferencia de cambio, mantenimiento de valor",
                    "(-)  Cargos por diferencia de cambio, mantenimiento de valor",
                    "RESULTADO DESPUES DE AJUSTE POR DIFERENCIA DE CAMBIO Y MANTENIMIENTO DE VALOR",
                ]),
                ("(=) RESULTADO NETO DEL EJERCICIO ANTES DE AJUSTES DE GESTIONES ANTERIORES", [
                    "(+/-) Ingresos (gastos) extraordinarios",
                ]),
                ("(=) RESULTADO ANTES DE IMPUESTOS Y AJUSTE CONTABLE POR EFECTO DE INFLACIÓN", [
                    "(+) Ingresos gestiones anteriores",
                    "(-) Gastos de gestiones anteriores",
                ]),
                ("(=) RESULTADO ANTES DE IMPUESTOS", [
                    "(+/-) Ajuste contable por efecto de la inflación",
                ]),
                ("(=) RESULTADO DE LA GESTIÓN", [
                    "(-) Impuestos sobre las utilidades de las empresas (IUE)",
                ]),
            ]

            income_lookup = {}
            for block_root, items in income_statement_blocks:
                income_lookup[normalize_text(block_root)] = (block_root, None)
                for item in items:
                    income_lookup[normalize_text(item)] = (block_root, item)

            alias_results = {
                normalize_text("RESULTADO FINANCIERO BRUTO"): "(=) RESULTADO FINANCIERO BRUTO",
                normalize_text("RESULTADO DE OPERACIÓN BRUTO"): "(=) RESULTADO DE OPERACIÓN BRUTO",
                normalize_text("RESULTADO DE OPERACIÓN  DESPUÉS DE INCOBRABLES"): "RESULTADO DE OPERACIÓN  DESPUÉS DE INCOBRABLES",
                normalize_text("RESULTADO DE OPERACIÓN NETO"): "RESULTADO DE OPERACIÓN NETO",
                normalize_text("RESULTADO DESPUES DE AJUSTE POR DIFERENCIA DE CAMBIO Y MANTENIMIENTO DE VALOR"): "RESULTADO DESPUES DE AJUSTE POR DIFERENCIA DE CAMBIO Y MANTENIMIENTO DE VALOR",
                normalize_text("RESULTADO NETO DEL EJERCICIO ANTES DE AJUSTES DE GESTIONES ANTERIORES"): "(=) RESULTADO NETO DEL EJERCICIO ANTES DE AJUSTES DE GESTIONES ANTERIORES",
                normalize_text("RESULTADO ANTES DE IMPUESTOS Y AJUSTE CONTABLE POR EFECTO DE INFLACIÓN"): "(=) RESULTADO ANTES DE IMPUESTOS Y AJUSTE CONTABLE POR EFECTO DE INFLACIÓN",
                normalize_text("RESULTADO ANTES DE IMPUESTOS"): "(=) RESULTADO ANTES DE IMPUESTOS",
                normalize_text("RESULTADO DE LA GESTIÓN"): "(=) RESULTADO DE LA GESTIÓN",
            }

            current_nv1 = None
            current_nv2 = None
            records = []

            for r in range(header_row + 1, len(df_raw)):
                raw_cell = df_raw.iloc[r, 0]
                if pd.isna(raw_cell) or not str(raw_cell).strip():
                    continue

                raw_text = str(raw_cell)
                label_clean = raw_text.strip()
                leading_spaces = len(raw_text) - len(raw_text.lstrip(" "))
                indent_level = cell_indents.get(r, 0)
                norm_label = normalize_text(label_clean)

                # Case A: Balance Sheet Root
                if norm_label in balance_roots:
                    current_nv1 = balance_roots[norm_label]
                    current_nv2 = None
                    nv1, nv2, nv3 = current_nv1, None, None
                # Case B: Income Statement Item or Component
                elif norm_label in income_lookup:
                    target_nv1, target_nv2 = income_lookup[norm_label]
                    current_nv1 = target_nv1
                    current_nv2 = target_nv2
                    nv1, nv2, nv3 = current_nv1, current_nv2, None
                # Case C: Income Statement Milestone Alias
                elif norm_label in alias_results:
                    mapped_target = alias_results[norm_label]
                    if mapped_target.startswith("(=)"):
                        current_nv1 = mapped_target
                        current_nv2 = None
                        nv1, nv2, nv3 = current_nv1, None, None
                    else:
                        nv1, nv2, nv3 = current_nv1, label_clean, None
                # Case D: Hierarchical child or chapter account
                else:
                    if indent_level >= 2 or leading_spaces >= 4:
                        nv1, nv2, nv3 = current_nv1, current_nv2, label_clean
                    else:
                        current_nv2 = label_clean
                        nv1, nv2, nv3 = current_nv1, current_nv2, None

                for col_idx, entity in entities.items():
                    val = df_raw.iloc[r, col_idx]
                    records.append({
                        "nv1": str(nv1) if nv1 is not None else None,
                        "nv2": str(nv2) if nv2 is not None else None,
                        "nv3": str(nv3) if nv3 is not None else None,
                        "nv4": str(entity) if entity is not None else None,
                        "fecha": str(cut_date),
                        "valor": val,
                    })

            df_data = pd.DataFrame(records)

            # Normalize numeric values
            df_data["valor"] = to_numeric_datax(df_data["valor"], decimal_separator=",").round()

            # Ensure proper string/None data types
            for col in ["nv1", "nv2", "nv3", "nv4", "fecha"]:
                df_data[col] = df_data[col].where(df_data[col].notna(), None)

            metadata_dict = {
                "file_name": file_name,
                "titles": titles if titles else ["ESTADOS FINANCIEROS POR ENTIDAD"],
                "page_number": int(page_number),
            }

            return metadata_dict, df_data

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
        """
        Validates accounting completeness and mathematical reconciliation:
        1. Vertical Hierarchy Reconciliation:
           a) Sum of child sub-accounts (nv3) equals their parent category (nv2).
              Example: Sum of Utilidades acumuladas + Utilidades del periodo equals RESULTADOS ACUMULADOS.
           b) Sum of chapter accounts (nv2) equals their root total (nv1).
              Example: Sum of DISPONIBILIDADES, INVERSIONES, etc. equals ACTIVO.
           c) Accounting Equation: ACTIVO == PASIVO + PATRIMONIO for each entity and date.
        2. Horizontal Reconciliation:
           For each row and date, the sum of individual entities (ACC + ACD)
           must equal TOTAL within TOLERANCE.

        Returns:
            False: Validation successful (data complete and mathematically consistent).
            True: Validation failed (discrepancy detected).
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if "valor" not in dataframe.columns or "fecha" not in dataframe.columns:
                return True

            df = dataframe.copy()
            df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator)

            # 1. Vertical Validation: Child accounts (nv3) summing to parent category (nv2)
            if "nv3" in df.columns and "nv2" in df.columns and "nv4" in df.columns:
                for (dt, ent), grp in df.groupby(["fecha", "nv4"]):
                    categories_with_children = grp[grp["nv3"].notna()]["nv2"].dropna().unique()
                    for cat in categories_with_children:
                        parent_row = grp[(grp["nv2"] == cat) & (grp["nv3"].isna())]
                        if parent_row.empty:
                            continue
                        parent_val = parent_row["valor_num"].iloc[0]
                        children_sum = grp[(grp["nv2"] == cat) & (grp["nv3"].notna())]["valor_num"].sum()
                        diff = abs(parent_val - children_sum)
                        if diff > TOLERANCE:
                            print(
                                f"Vertical validation error in {ent} ({dt}) - nv2 '{cat}': "
                                f"Parent ({parent_val:.2f}) differs from sum of nv3 children ({children_sum:.2f}) by {diff:.2f}"
                            )
                            return True

            # 2. Vertical Validation: Chapters (nv2) summing to root totals (nv1: ACTIVO, PASIVO, PATRIMONIO)
            if "nv1" in df.columns and "nv2" in df.columns and "nv4" in df.columns:
                for (dt, ent), grp in df.groupby(["fecha", "nv4"]):
                    for root in ["ACTIVO", "PASIVO", "PATRIMONIO"]:
                        root_row = grp[(grp["nv1"] == root) & (grp["nv2"].isna())]
                        if root_row.empty:
                            continue
                        root_val = root_row["valor_num"].iloc[0]
                        chapters_sum = grp[(grp["nv1"] == root) & (grp["nv2"].notna()) & (grp["nv3"].isna())]["valor_num"].sum()
                        diff = abs(root_val - chapters_sum)
                        if diff > TOLERANCE:
                            print(
                                f"Vertical validation error in {ent} ({dt}) - nv1 '{root}': "
                                f"Root ({root_val:.2f}) differs from sum of nv2 chapters ({chapters_sum:.2f}) by {diff:.2f}"
                            )
                            return True

            # 3. Accounting Balance Identity: ACTIVO == PASIVO + PATRIMONIO per entity
            if "nv4" in df.columns and "nv1" in df.columns:
                for (dt, ent), grp in df.groupby(["fecha", "nv4"]):
                    act_rows = grp[(grp["nv1"] == "ACTIVO") & (grp["nv2"].isna())]
                    pas_rows = grp[(grp["nv1"] == "PASIVO") & (grp["nv2"].isna())]
                    pat_rows = grp[(grp["nv1"] == "PATRIMONIO") & (grp["nv2"].isna())]

                    if not act_rows.empty and not pas_rows.empty and not pat_rows.empty:
                        act_val = act_rows["valor_num"].iloc[0]
                        expected_pas_pat = pas_rows["valor_num"].iloc[0] + pat_rows["valor_num"].iloc[0]
                        diff = abs(act_val - expected_pas_pat)
                        if diff > TOLERANCE:
                            print(
                                f"Accounting identity error in {ent} ({dt}): "
                                f"ACTIVO ({act_val:.2f}) != PASIVO + PATRIMONIO ({expected_pas_pat:.2f}) by {diff:.2f}"
                            )
                            return True

            # 4. Horizontal Reconciliation: Sum of individual entities equals TOTAL
            group_cols = [c for c in ["nv1", "nv2", "nv3", "fecha"] if c in df.columns]
            for keys, grp in df.groupby(group_cols, dropna=False):
                tot_row = grp[grp["nv4"] == "TOTAL"]
                comp_rows = grp[grp["nv4"] != "TOTAL"]

                if tot_row.empty:
                    continue

                expected_tot = tot_row["valor_num"].iloc[0]
                calculated_tot = comp_rows["valor_num"].sum()

                diff = abs(calculated_tot - expected_tot)
                if diff > TOLERANCE:
                    print(
                        f"Horizontal validation error in row {keys}: Entities sum ({calculated_tot:.2f}) "
                        f"differs from TOTAL ({expected_tot:.2f}) by {diff:.2f}"
                    )
                    return True

            return False

        except Exception as error:
            import traceback; traceback.print_exc()
            print(f"Validation exception: {error}")
            return True


Robot = D_BO_000000054_01
Executor_D_BO_000000054_01 = D_BO_000000054_01