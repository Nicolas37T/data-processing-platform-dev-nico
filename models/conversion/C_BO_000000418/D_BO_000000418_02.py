import os
import re
import traceback
from typing import Tuple
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000418_02(Conversion_Base):
    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        try:
            import openpyxl

            file_name = os.path.basename(file_path)

            wb = openpyxl.load_workbook(file_path, data_only=True)

            def _find_pas_sheet(workbook):
                if "PAS" in workbook.sheetnames:
                    return workbook["PAS"]
                for sname in workbook.sheetnames:
                    ws = workbook[sname]
                    a1 = str(ws.cell(1, 1).value or "").upper()
                    if "BANCO" in a1 or "TASAS" in a1 or "BCB" in a1:
                        return ws
                return workbook[workbook.sheetnames[0]]

            sheet = _find_pas_sheet(wb)

            # Detect format: if header has nv1, fecha, and valor, treat as tabular
            header_row1 = [
                str(sheet.cell(1, c).value or "").strip().lower()
                for c in range(1, 13)
            ]
            is_tabular_format = (
                "nv1" in header_row1 and "fecha" in header_row1 and "valor" in header_row1
            )

            REQUIRED_NV = ["nv1", "nv2", "nv3", "nv4", "nv5"]

            if is_tabular_format:
                df_raw = pd.read_excel(file_path, sheet_name=sheet.title)
                titulo_cols = [c for c in df_raw.columns if str(c).startswith("titulo")]
                titles_vals = []
                for tc in sorted(titulo_cols):
                    v = df_raw[tc].dropna()
                    if not v.empty:
                        titles_vals.append(str(v.iloc[0]).strip())
                titles = titles_vals if titles_vals else [
                    "Banco Central de Bolivia",
                    "Información sobre el Interés que Perciben los Ahorristas por sus Depósitos",
                ]

                for nv in REQUIRED_NV:
                    if nv not in df_raw.columns:
                        df_raw[nv] = None

                fecha_col = "fecha" if "fecha" in df_raw.columns else None
                valor_col = "valor" if "valor" in df_raw.columns else None

                if not fecha_col or not valor_col:
                    raise ValueError("Tabular file missing 'fecha' or 'valor' columns")

                df_melted = df_raw[REQUIRED_NV + [fecha_col, valor_col]].copy()
                df_melted.columns = REQUIRED_NV + ["fecha", "valor"]
                df_melted["fecha"] = pd.to_datetime(df_melted["fecha"]).dt.strftime("%Y-%m-%d")
                df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=".")
                for col in REQUIRED_NV:
                    df_melted[col] = df_melted[col].where(df_melted[col].notna(), None)

                metadata = {
                    "file_name": file_name,
                    "titles": titles,
                    "page_number": int(page_number),
                }
                return metadata, df_melted

            # Parse BCB visual layout (PAS sheet)
            month_map = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
            }

            def parse_report_date(text: str) -> str:
                m = re.search(
                    r"al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    day, mon_str, year = m.groups()
                    mon = month_map.get(mon_str.lower(), 1)
                    return f"{int(year):04d}-{mon:02d}-{int(day):02d}"
                m2 = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", file_name)
                if m2:
                    return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
                m3 = re.search(r"(\d{4})[-_](\d{2})", file_name)
                if m3:
                    y, mo = int(m3.group(1)), int(m3.group(2))
                    import calendar
                    return f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
                return pd.Timestamp.now().strftime("%Y-%m-%d")

            titles = []
            report_date = None

            for r in range(1, 6):
                val = str(sheet.cell(r, 1).value or "").strip()
                if not val:
                    continue
                titles.append(val)
                if report_date is None and re.search(r"\d{4}", val):
                    report_date = parse_report_date(val)

            if report_date is None:
                report_date = parse_report_date("")

            # Column mapping for cols 2 to 19 (Moneda Nacional and Moneda Extranjera)
            col_map = {
                2: ("Moneda Nacional", "Caja de Ahorro", "Sin Plazo"),
                3: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "30"),
                4: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "60"),
                5: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "90"),
                6: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "180"),
                7: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "360"),
                8: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "720"),
                9: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "1080"),
                10: ("Moneda Nacional", "Depósitos a Plazo Fijo (Días)", "Mayor"),
                11: ("Moneda Extranjera", "Caja de Ahorro", "Sin Plazo"),
                12: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "30"),
                13: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "60"),
                14: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "90"),
                15: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "180"),
                16: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "360"),
                17: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "720"),
                18: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "1080"),
                19: ("Moneda Extranjera", "Depósitos a Plazo Fijo (Días)", "Mayor"),
            }

            def identify_group(text: str) -> str:
                clean = re.sub(r"[^A-Z ]", "", text.upper())
                clean = " ".join(clean.split())
                if "MICROFINANZAS" in clean:
                    return "Entidades Especializadas en Microfinanzas"
                if "PYME" in clean:
                    return "Bancos PYME"
                if "VIVIENDA" in clean:
                    return "Entidades Financieras de Vivienda"
                if "COOPERATIVA" in clean:
                    return "Cooperativas"
                if "DESARROLLO" in clean:
                    return "Instituciones Financieras de Desarrollo"
                if "BANCO" in clean and "MULTIPLE" in clean:
                    return "Bancos Múltiples"
                return None

            current_group = "Bancos Múltiples"
            records = []
            STOP_KEYWORDS = {"FUENTE", "ELABORACI", "(1)VIGENTE", "(1)", "(2)"}

            for r in range(10, sheet.max_row + 1):
                c1_cell = sheet.cell(r, 1)
                c1_val = str(c1_cell.value or "").strip()

                if not c1_val:
                    continue

                if any(kw in c1_val.upper() for kw in STOP_KEYWORDS):
                    break

                is_bold = c1_cell.font.bold if c1_cell.font else False
                has_numeric = any(
                    isinstance(sheet.cell(r, c).value, (int, float))
                    and sheet.cell(r, c).value is not None
                    for c in col_map
                )

                if is_bold and not has_numeric:
                    grp = identify_group(c1_val)
                    if grp:
                        if grp == "Bancos Múltiples" and current_group == "Entidades Especializadas en Microfinanzas":
                            pass
                        else:
                            current_group = grp
                    continue

                if not has_numeric:
                    continue

                bank_name = c1_val.strip()
                for col_idx, (moneda, tipo, plazo) in col_map.items():
                    raw = sheet.cell(r, col_idx).value
                    valor = raw if isinstance(raw, (int, float)) else 0.0
                    records.append({
                        "nv1": current_group,
                        "nv2": bank_name,
                        "nv3": moneda,
                        "nv4": tipo,
                        "nv5": plazo,
                        "fecha": report_date,
                        "valor": valor,
                    })

            df_melted = pd.DataFrame(records, columns=REQUIRED_NV + ["fecha", "valor"])
            if not df_melted.empty:
                df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=".")
                for col in REQUIRED_NV + ["fecha"]:
                    df_melted[col] = df_melted[col].where(df_melted[col].notna(), None)

            metadata = {
                "file_name": file_name,
                "titles": titles or [
                    "Banco Central de Bolivia",
                    "Información sobre el Interés que Perciben los Ahorristas por sus Depósitos",
                ],
                "page_number": int(page_number),
            }
            return metadata, df_melted

        except Exception:
            traceback.print_exc()
            return "", pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Validates the flattened data.
        Returns False if data is valid, True if discrepancies are found.

        This report contains interest RATES (tasas pasivas), not account sums,
        so hierarchical reconciliation does not apply.
        We validate that all rate values are non-negative.
        """
        try:
            if dataframe is None or dataframe.empty:
                return True
            df = dataframe.copy()
            if pd.api.types.is_numeric_dtype(df["valor"]):
                df["valor_num"] = df["valor"].astype(float)
            else:
                df["valor_num"] = to_numeric_datax(df["valor"], decimal_separator)

            # All interest rates must be >= 0
            if (df["valor_num"] < 0).any():
                return True

            return False
        except Exception:
            traceback.print_exc()
            return True


Executor_D_BO_000000418_02 = D_BO_000000418_02
Robot = D_BO_000000418_02
