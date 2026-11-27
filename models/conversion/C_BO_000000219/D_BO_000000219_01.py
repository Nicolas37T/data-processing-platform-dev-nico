from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
import pandas as pd
import xlrd
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000219_01(Conversion_Base):
    """Conversion robot for D_BO_000000219_01: BCB - Cotización de Otras Monedas."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """
        Extract daily exchange rates, UFV, metals, DEG, and SOFR from BCB XLS files.

        Returns:
            tuple: (metadata_dict, df_melted) with levels nv1..nv5, fecha, valor.
        """
        file_name = os.path.basename(file_path)
        print("Converting:", file_name)
        try:
            def clean_text(val):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return None
                text = re.sub(r"\s+", " ", str(val)).strip()
                text = re.sub(r"\*+$", "", text).strip()
                return text or None

            months_es = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
            }

            wb = xlrd.open_workbook(file_path, ignore_workbook_corruption=True)
            sheet_idx = int(page_number) - 1 if int(page_number) >= 1 else 0
            if sheet_idx >= wb.nsheets:
                sheet_idx = 0
            sheet = wb.sheet_by_index(sheet_idx)

            # 1. Extract publication date from header (fallback to filename YYYY-MM-DD)
            fecha_str = None
            re_header_date = re.compile(
                r"DEL\s+(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÑ]+)\s+DE\s+(\d{4})",
                re.IGNORECASE,
            )
            for r in range(min(15, sheet.nrows)):
                for c in range(min(5, sheet.ncols)):
                    cell_txt = clean_text(sheet.cell_value(r, c))
                    if not cell_txt:
                        continue
                    m = re_header_date.search(cell_txt)
                    if m:
                        day = int(m.group(1))
                        mon_num = months_es.get(m.group(2).lower())
                        year = int(m.group(3))
                        if mon_num:
                            fecha_str = pd.Timestamp(year=year, month=mon_num, day=day).strftime(format)
                            break
                if fecha_str:
                    break

            if not fecha_str:
                fn_match = re.match(r"^(\d{4}-\d{2}-\d{2})", file_name)
                if fn_match:
                    fecha_str = pd.to_datetime(fn_match.group(1)).strftime(format)
                else:
                    raise ValueError(f"Could not extract date from {file_name}")

            # 2. Parse sections dynamically
            section_anchors = (
                "cotizacion oficial",
                "cotizacion de monedas",
                "cotizacion de ufv",
                "cotizacion de metales",
                "derechos especiales de giro",
                "tasa sofr",
            )
            header_markers = {"pais / concepto", "pais / region", "metal", "fmi", "concepto"}

            records = []
            current_section = None
            col_headers = {}

            for r in range(sheet.nrows):
                row_vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                c0 = clean_text(row_vals[0]) if len(row_vals) > 0 else None

                if not c0:
                    continue
                c0_low = c0.lower()

                # Stop at footnotes
                if c0.startswith("*") or c0_low.startswith("la tasa sofr") or c0_low.startswith("las cotizaciones"):
                    continue

                # Check if row opens a new section
                if any(c0_low.startswith(anchor) for anchor in section_anchors):
                    current_section = c0
                    col_headers = {}
                    continue

                if not current_section:
                    continue

                # Check if row is a table header row inside the current section
                if c0_low in header_markers:
                    col_headers = {}
                    for c_idx in range(3, len(row_vals)):
                        h_txt = clean_text(row_vals[c_idx])
                        if h_txt:
                            col_headers[c_idx] = h_txt
                    continue

                # Otherwise treat as data row when numeric values exist in columns >= 3
                nv2 = c0
                nv3 = clean_text(row_vals[1]) if len(row_vals) > 1 else None
                nv4 = clean_text(row_vals[2]) if len(row_vals) > 2 else None

                # For UFV section without explicit header row, assign default metric header
                if not col_headers and "ufv" in current_section.lower():
                    col_headers = {3: "Tipo de Cambio (Bs/UFV)"}

                for c_idx, metric_label in col_headers.items():
                    if c_idx >= len(row_vals):
                        continue
                    raw_val = row_vals[c_idx]
                    if raw_val is None or str(raw_val).strip() == "":
                        continue
                    try:
                        num_val = float(str(raw_val).replace(",", "").strip())
                    except (ValueError, TypeError):
                        continue

                    records.append({
                        "nv1": current_section,
                        "nv2": nv2,
                        "nv3": nv3,
                        "nv4": nv4,
                        "nv5": metric_label,
                        "fecha": fecha_str,
                        "valor": num_val,
                    })

            df_melted = pd.DataFrame(records, columns=["nv1", "nv2", "nv3", "nv4", "nv5", "fecha", "valor"])
            if df_melted.empty:
                raise ValueError(f"No data rows extracted from {file_name}")

            df_melted["valor"] = pd.to_numeric(df_melted["valor"], errors="coerce")
            df_melted = df_melted.dropna(subset=["valor"]).reset_index(drop=True)

            titles = [
                "BANCO CENTRAL DE BOLIVIA",
                "GERENCIA DE OPERACIONES INTERNACIONALES",
                "TABLA DE COTIZACIONES",
            ]

            return (
                {
                    "file_name": file_name,
                    "titles": titles,
                    "page_number": int(page_number),
                },
                df_melted,
            )

        except Exception as e:
            print(f"An error occurred in extraction: {e}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Validate that extracted exchange rate values are present and numeric.
        Returns False when valid, True on error.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True

            df = dataframe.copy()
            if not pd.api.types.is_numeric_dtype(df["valor"]):
                raw_str = df["valor"].astype(str).str.strip()
                if decimal_separator == "," and raw_str.str.contains(",", regex=False).any():
                    df["valor"] = to_numeric_datax(serie=df["valor"], decimal_separator=decimal_separator)
                else:
                    df["valor"] = pd.to_numeric(raw_str, errors="coerce")

            if df["valor"].dropna().empty:
                return True

            return False
        except Exception as e:
            print(f"Validation error: {e}")
            traceback.print_exc()
            return True


Executor_D_BO_000000219_01 = D_BO_000000219_01
Robot = D_BO_000000219_01
