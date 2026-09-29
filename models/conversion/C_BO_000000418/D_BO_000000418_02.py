from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
from typing import Tuple

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

            # ------------------------------------------------------------------
            # Helper: parse the report date from the header text.
            # The header contains "Semana del D1 al D2 de MES de YYYY",
            # so we use the end-of-week day as the report date.
            # ------------------------------------------------------------------
            def parse_report_date(text: str) -> str:
                month_map = {
                    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
                }
                # "Semana del 3 al 9 de agosto de 2026"
                m = re.search(
                    r"al\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    day, mon_str, year = m.groups()
                    mon = month_map.get(mon_str.lower(), 1)
                    return f"{int(year):04d}-{mon:02d}-{int(day):02d}"
                # Fallback: try YYYY-MM from filename
                m2 = re.search(r"(\d{4})[-_](\d{2})", file_name)
                if m2:
                    y, mo = int(m2.group(1)), int(m2.group(2))
                    import calendar
                    return f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
                return pd.Timestamp.now().strftime("%Y-%m-%d")

            # ------------------------------------------------------------------
            # Load workbook - target sheet: "PAS" (fallback: auto-detect)
            # ------------------------------------------------------------------
            wb = openpyxl.load_workbook(file_path, data_only=True)

            def _find_pas_sheet(workbook):
                """Find the sheet with tasas pasivas data."""
                # Priority 1: exact name 'PAS'
                if "PAS" in workbook.sheetnames:
                    return workbook["PAS"]
                # Priority 2: look for sheet whose A1 contains 'BANCO CENTRAL' or 'TASAS'
                for sname in workbook.sheetnames:
                    ws = workbook[sname]
                    a1 = str(ws.cell(1, 1).value or "").upper()
                    if "BANCO" in a1 or "TASAS" in a1 or "BCB" in a1:
                        return ws
                # Priority 3: largest sheet (most data)
                return workbook[workbook.sheetnames[0]]

            sheet = _find_pas_sheet(wb)

            # ------------------------------------------------------------------
            # Detect format: if Sheet1 header is tabular (nv1/nv2/fecha/valor),
            # read it directly instead of parsing the visual BCB layout.
            # ------------------------------------------------------------------
            header_row1 = [str(sheet.cell(1, c).value or "").strip().lower()
                           for c in range(1, 13)]
            is_tabular_format = "nv1" in header_row1 and "fecha" in header_row1 and "valor" in header_row1

            if is_tabular_format:
                # Already-processed tabular file: read as DataFrame directly
                df_raw = pd.read_excel(file_path, sheet_name=sheet.title)
                # Build metadata from titulo columns
                titulo_cols = [c for c in df_raw.columns if str(c).startswith("titulo")]
                titles_vals = []
                for tc in sorted(titulo_cols):
                    v = df_raw[tc].dropna()
                    if not v.empty:
                        titles_vals.append(str(v.iloc[0]).strip())
                titles = titles_vals if titles_vals else ["Tasas Pasivas - BCB"]

                # Get nv/fecha/valor columns
                nv_cols = sorted([c for c in df_raw.columns if str(c).startswith("nv")])
                fecha_col = "fecha" if "fecha" in df_raw.columns else None
                valor_col = "valor" if "valor" in df_raw.columns else None

                if not fecha_col or not valor_col:
                    raise ValueError("Tabular file missing 'fecha' or 'valor' columns")

                df_melted = df_raw[nv_cols + [fecha_col, valor_col]].copy()
                df_melted.columns = nv_cols + ["fecha", "valor"]

                # Ensure always exactly nv1..nv6 to match template structure
                REQUIRED_NV = ["nv1", "nv2", "nv3", "nv4", "nv5", "nv6"]
                for nv in REQUIRED_NV:
                    if nv not in df_melted.columns:
                        # Insert missing nv column before 'fecha'
                        fecha_idx = df_melted.columns.get_loc("fecha")
                        df_melted.insert(fecha_idx, nv, None)

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

            # ------------------------------------------------------------------
            # Step 1: Extract header metadata (rows 1-5)
            # Row 1: institution name
            # Row 2: report title
            # Row 3: date range + unit
            # Row 4: section label "TASAS PASIVAS*"
            # ------------------------------------------------------------------
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

            # ------------------------------------------------------------------
            # Step 2: Build column map from the 3-level header (rows 6-8)
            # Each data column maps to (moneda, tipo_deposito, plazo)
            # ------------------------------------------------------------------
            row6 = {c: str(sheet.cell(6, c).value or "").strip() for c in range(1, 22)}
            row7 = {c: str(sheet.cell(7, c).value or "").strip() for c in range(1, 22)}
            row8 = {c: sheet.cell(8, c).value for c in range(1, 22)}

            # Forward-fill currency group (row 6) per column
            col_currency = {}
            current_currency = None
            for c in range(1, 22):
                v6 = row6.get(c, "")
                if v6 and v6.upper() not in ("ENTIDADES", ""):
                    current_currency = v6
                if current_currency and c > 1:
                    col_currency[c] = current_currency

            # Forward-fill deposit type (row 7) per column
            col_tipo = {}
            current_tipo = None
            for c in range(2, 22):
                v7 = row7.get(c, "")
                if v7:
                    current_tipo = v7
                if current_tipo:
                    col_tipo[c] = current_tipo

            # Build final column descriptors: col -> (moneda, tipo, plazo)
            col_map = {}
            for c in range(2, 22):
                moneda = col_currency.get(c)
                tipo = col_tipo.get(c)
                plazo = row8.get(c)
                if moneda and tipo:
                    if plazo is not None:
                        col_map[c] = (moneda, tipo, str(plazo))
                    elif tipo in ("Caja de Ahorro", "Promedio"):
                        col_map[c] = (moneda, tipo, "-")

            # ------------------------------------------------------------------
            # Step 3: Traverse data rows
            # Bold rows without numeric data -> section/sub-section headers
            # Non-bold rows with numeric data -> entity records
            # ------------------------------------------------------------------
            DATA_START = 10
            STOP_KEYWORDS = {"FUENTE", "ELABORACI", "(1)VIGENTE", "(1)", "(2)"}

            records = []
            current_nv1 = None
            current_nv2 = None

            for r in range(DATA_START, sheet.max_row + 1):
                c1_cell = sheet.cell(r, 1)
                c1_val = str(c1_cell.value or "").strip()

                if not c1_val:
                    continue

                # Stop at footnotes/source lines
                if any(kw in c1_val.upper() for kw in STOP_KEYWORDS):
                    break

                is_bold = c1_cell.font.bold if c1_cell.font else False

                raw_values = [sheet.cell(r, c).value for c in col_map]
                has_numeric = any(
                    isinstance(v, (int, float)) and v is not None for v in raw_values
                )

                # Bold header row - update hierarchical state BEFORE numeric check
                if is_bold and not has_numeric:
                    normalized = re.sub(r"[^A-Z ]", "", c1_val.upper())
                    normalized = " ".join(normalized.split())

                    # True top-level sections (nv1). These reset nv2 to None.
                    NV1_ANCHORS = {
                        "BANCOS MULTIPLES",
                        "ENTIDADES ESPECIALIZADAS EN MICROFINANZAS",
                        "INSTITUCIONES FINANCIERAS DE DESARROLLO",
                    }

                    if current_nv1 is None or normalized in NV1_ANCHORS:
                        # First header OR a true top-level anchor -> set nv1
                        current_nv1 = c1_val
                        current_nv2 = None
                    else:
                        # Sub-sector inside a top-level section -> set nv2
                        # e.g. BANCOS MULTIPLES (2nd), BANCOS PYME,
                        # COOPERATIVAS, ENTIDADES FINANCIERAS DE VIVIENDA
                        current_nv2 = c1_val
                    continue

                if not has_numeric:
                    continue

                # Emit one record per data column
                for col_idx, (moneda, tipo, plazo) in col_map.items():
                    raw = sheet.cell(r, col_idx).value
                    valor = raw if isinstance(raw, (int, float)) else 0.0
                    records.append({
                        "nv1": current_nv1,
                        "nv2": current_nv2,
                        "nv3": c1_val,
                        "nv4": moneda,
                        "nv5": tipo,
                        "nv6": plazo,
                        "fecha": report_date,
                        "valor": valor,
                    })

            df_melted = pd.DataFrame(records)
            if not df_melted.empty:
                df_melted["valor"] = to_numeric_datax(df_melted["valor"], decimal_separator=".")
                for col in ["nv1", "nv2", "nv3", "nv4", "nv5", "nv6", "fecha"]:
                    df_melted[col] = df_melted[col].where(df_melted[col].notna(), None)

            metadata = {
                "file_name": file_name,
                "titles": titles,
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
            import traceback; traceback.print_exc()
            return True



Executor_D_BO_000000418_02 = D_BO_000000418_02
Robot = D_BO_000000418_02
