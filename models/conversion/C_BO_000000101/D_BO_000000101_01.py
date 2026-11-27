from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import calendar
import datetime
import traceback
import unicodedata
import openpyxl
import pandas as pd
import numpy as np

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000101_01(Conversion_Base):
    """
    Conversion robot for Base Monetaria Origen report (D_BO_000000101_01).
    Processes central bank monetary base source statistics into a normalized
    melted structure with strict accounting consistency validation.
    """

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d"
    ) -> tuple:
        """
        Extracts monetary base origin table from an Excel file into a melted
        DataFrame and metadata dictionary.

        Args:
            file_path: Absolute path to the source Excel file.
            key_words: Filter keywords (if any).
            template_path: Path to template reference (if any).
            page_number: Sheet page index (1-indexed).
            format: Target date format string.

        Returns:
            tuple: (metadata_dict, df_melted)
        """
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            sheet_idx = page_number - 1 if 0 <= page_number - 1 < len(workbook.worksheets) else 0
            sheet = workbook.worksheets[sheet_idx]

            # 1. Anchor detection: find cell with 'ORIGEN'
            anchor_row = None
            anchor_col = None

            for r in range(1, min(25, sheet.max_row + 1)):
                for c in range(1, min(27, sheet.max_column + 1)):
                    cell_val = sheet.cell(r, c).value
                    if cell_val is not None:
                        clean_str = re.sub(r"\s+", " ", str(cell_val)).strip()
                        if re.match(r"^O\s*R\s*I\s*G\s*E\s*N$", clean_str, re.IGNORECASE):
                            anchor_row = r
                            anchor_col = c
                            break
                if anchor_row is not None:
                    break

            if anchor_row is None:
                anchor_row = 5
                anchor_col = 2

            # 2. Find end_col (before DESTINO)
            end_col = anchor_col + 10
            for c in range(anchor_col + 1, min(30, sheet.max_column + 1)):
                cell_val = sheet.cell(anchor_row, c).value
                if cell_val is not None:
                    txt = re.sub(r"\s+", "", str(cell_val)).strip().upper()
                    if "DESTINO" in txt:
                        end_col = c - 1
                        break

            # 3. Find first_data_row after anchor
            first_data_row = anchor_row + 1
            while first_data_row <= sheet.max_row:
                val = sheet.cell(first_data_row, anchor_col).value
                if isinstance(val, (int, float)):
                    break
                first_data_row += 1

            # 4. Build column definitions for Origen section
            columns_info = []
            for col_idx in range(anchor_col, end_col + 1):
                parts = []
                for r in range(anchor_row + 1, first_data_row):
                    val = sheet.cell(r, col_idx).value
                    if val is not None:
                        txt = str(val).strip()
                        if txt:
                            parts.append(txt)

                combined_header = " ".join(parts)
                combined_header = re.sub(r"\bIntrumentos\b", "Instrumentos", combined_header)
                combined_header = re.sub(r"\s+", " ", combined_header).strip()

                offset = col_idx - anchor_col
                # Offset mapping aligned with historical standard
                if offset in [4, 5, 6, 7, 8]:
                    nv2 = "Crédito a Bancos"
                    if offset == 4:
                        nv3 = "Crédito a Bancos Total CB=BCL+OEF"
                    elif offset == 5:
                        nv3 = "BCL"
                    elif offset == 6:
                        nv3 = "BE y OEF (1)"
                    elif offset == 7:
                        nv3 = 'CD+LT "D"+BT"D" OMA'
                    elif offset == 8:
                        nv3 = "Otros Instrumentos de regulación Monetaria ORM(2)"
                else:
                    if offset == 0:
                        nv2 = "Reservas Internacionales Netas RIN = RIB - OECP"
                    elif offset == 1:
                        nv2 = "Reservas Internacionales Brutas RIB"
                    elif offset == 2:
                        nv2 = "Obligaciones con el exterior a corto plazo OECP"
                    elif offset == 3:
                        nv2 = "Crédito Neto al Sector Público CNSP"
                    elif offset == 9:
                        nv2 = "Otras Cuentas Netas (OC)"
                    elif offset == 10:
                        nv2 = "BASE MONETARIA (BM)"
                    else:
                        nv2 = combined_header
                    nv3 = None

                columns_info.append((col_idx, nv2, nv3))

            # 5. Extract time-series data rows
            month_map = {
                "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12
            }

            records = []
            curr_year = None

            for r in range(1, sheet.max_row + 1):
                # Skip header rows
                if anchor_row <= r < first_data_row:
                    continue

                c1 = sheet.cell(r, 1).value
                c2 = sheet.cell(r, 2).value

                str_period = str(c1).strip() if c1 is not None else ""
                if re.match(r"^(FUENTE|ELABORACI[OÓ]N|NOTAS?)\b", str_period, re.IGNORECASE):
                    break

                date_str = None

                # 5a. Date from c1 (annual or full date)
                if c1 is not None:
                    if isinstance(c1, (datetime.datetime, datetime.date)):
                        year = c1.year
                        month = c1.month
                        _, last_day = calendar.monthrange(year, month)
                        date_str = f"{year:04d}-{month:02d}-{last_day:02d}"
                    elif isinstance(c1, (int, float)):
                        yr = int(c1)
                        if 1900 <= yr <= 2100:
                            curr_year = yr
                            val_anchor = sheet.cell(r, anchor_col).value
                            if isinstance(val_anchor, (int, float)) and not c2:
                                date_str = f"{curr_year:04d}-12-31"
                    else:
                        m = re.search(r"(\d{4})", str_period)
                        if m:
                            yr = int(m.group(1))
                            if 1900 <= yr <= 2100:
                                curr_year = yr
                                val_anchor = sheet.cell(r, anchor_col).value
                                if isinstance(val_anchor, (int, float)) and not c2:
                                    date_str = f"{curr_year:04d}-12-31"

                # 5b. Monthly date from c2 with curr_year
                if not date_str and c2 is not None and curr_year:
                    m_str = re.sub(r"[^A-Z]", "", str(c2).upper()[:3])
                    if m_str in month_map:
                        val_anchor = sheet.cell(r, anchor_col).value
                        if isinstance(val_anchor, (int, float)):
                            mo = month_map[m_str]
                            _, last_day = calendar.monthrange(curr_year, mo)
                            date_str = f"{curr_year:04d}-{mo:02d}-{last_day:02d}"

                if not date_str:
                    continue

                for col_idx, nv2, nv3 in columns_info:
                    val = sheet.cell(r, col_idx).value
                    if val is not None:
                        records.append({
                            "nv1": "ORIGEN",
                            "nv2": nv2,
                            "nv3": nv3,
                            "fecha": date_str,
                            "valor": val
                        })

            df_melted = pd.DataFrame(records)

            if df_melted.empty:
                return {}, pd.DataFrame()

            # Hybrid numeric conversion & scientific notation handling
            df_melted["valor"] = pd.to_numeric(df_melted["valor"], errors="coerce")
            df_melted = df_melted.dropna(subset=["valor"])
            df_melted["valor"] = df_melted["valor"].apply(
                lambda x: np.format_float_positional(x, trim="-") if pd.notna(x) else x
            )

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": ["BASE MONETARIA", "(En miles de bolivianos)"],
                "page_number": int(page_number)
            }

            return metadata_dict, df_melted

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return {}, pd.DataFrame()

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0
    ) -> bool:
        """
        Validates accounting consistency of extracted monetary base origin data.
        Returns False if mathematical reconciliations hold within TOLERANCE.
        Returns True if discrepancies exceed TOLERANCE.
        """
        try:
            if dataframe.empty or "valor" not in dataframe.columns:
                return False

            df = dataframe.copy()
            # Safe numeric conversion tolerant to both dots and commas
            df["numeric_value"] = pd.to_numeric(
                df["valor"].astype(str).str.replace(",", "."),
                errors="coerce"
            )
            df = df.dropna(subset=["numeric_value"])

            # 1. Validation 1: RIN = RIB - OECP
            rin_rows = df[df["nv2"].str.contains(r"\bRIN\s*=", na=False, regex=True)][["fecha", "numeric_value"]].rename(columns={"numeric_value": "RIN"})
            rib_rows = df[df["nv2"].str.contains(r"Brutas\s+RIB\b", na=False, regex=True)][["fecha", "numeric_value"]].rename(columns={"numeric_value": "RIB"})
            oecp_rows = df[df["nv2"].str.contains(r"corto\s+plazo\s+OECP\b", na=False, regex=True)][["fecha", "numeric_value"]].rename(columns={"numeric_value": "OECP"})

            if not rin_rows.empty and not rib_rows.empty and not oecp_rows.empty:
                rin_merged = rin_rows.merge(rib_rows, on="fecha").merge(oecp_rows, on="fecha")
                rin_merged["diff"] = (rin_merged["RIN"] - (rin_merged["RIB"] - rin_merged["OECP"])).abs()
                max_rin_diff = rin_merged["diff"].max()
                if max_rin_diff > TOLERANCE:
                    print(f"Validation failure in RIN = RIB - OECP: max diff = {max_rin_diff} > {TOLERANCE}")
                    return True

            # 2. Validation 2: Total CB = BCL + BE y OEF (1)
            cb_tot = df[(df["nv2"] == "Crédito a Bancos") & (df["nv3"].str.contains(r"Total\s+CB", na=False, regex=True))][["fecha", "numeric_value"]].rename(columns={"numeric_value": "CB_TOT"})
            bcl = df[(df["nv2"] == "Crédito a Bancos") & (df["nv3"] == "BCL")][["fecha", "numeric_value"]].rename(columns={"numeric_value": "BCL"})
            be_oef = df[(df["nv2"] == "Crédito a Bancos") & (df["nv3"].str.contains(r"BE\s+y\s+OEF", na=False, regex=True))][["fecha", "numeric_value"]].rename(columns={"numeric_value": "BE_OEF"})

            if not cb_tot.empty and not bcl.empty and not be_oef.empty:
                cb_merged = cb_tot.merge(bcl, on="fecha").merge(be_oef, on="fecha")
                cb_merged["diff"] = (cb_merged["CB_TOT"] - (cb_merged["BCL"] + cb_merged["BE_OEF"])).abs()
                max_cb_diff = cb_merged["diff"].max()
                if max_cb_diff > TOLERANCE:
                    print(f"Validation failure in Total CB = BCL + BE y OEF: max diff = {max_cb_diff} > {TOLERANCE}")
                    return True

            return False

        except Exception as error:
            print(f"Error during validation: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000101_01 = D_BO_000000101_01
Robot = D_BO_000000101_01
