from models.conversion.Conversion_Base import Conversion_Base
"""
Conversion robot for report D_BO_000000126_01:
Financiamiento Concedido por el Banco Central al Sector Público.
"""

import os
import re
import calendar
import traceback
import numpy as np
import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax

class D_BO_000000126_01(Conversion_Base):
    """
    Conversion robot for report D_BO_000000126_01:
    'Financiamiento Concedido por el Banco Central al Sector Público'.
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
        Extracts financing data granted by the Central Bank to the
        public sector, normalizing time-series matrix data into a
        melted tabular format.

        Parameters
        ----------
        file_path : str
            Absolute path to the downloaded Excel file.
        key_words : str
            Keywords to validate or locate the target report.
        template_path : str
            Path to reference template (if applicable).
        page_number : int
            Sheet index or page number (defaults to 1).
        format : str
            Target date format string (defaults to '%Y-%m-%d').

        Returns
        -------
        tuple
            (metadata_dict, df_melted) where metadata_dict contains
            report metadata and df_melted contains [nv1, nv2, fecha, valor].
        """
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet_idx = (
                page_number - 1
                if page_number and page_number > 0
                else 0
            )
            sheet_names = wb.sheetnames
            sheet_name = (
                sheet_names[sheet_idx]
                if sheet_idx < len(sheet_names)
                else sheet_names[0]
            )
            ws = wb[sheet_name]

            # Extract metadata titles from top rows (rows 1 to 3)
            titles = []
            for r in range(1, 4):
                for c in range(1, ws.max_column + 1):
                    val = ws.cell(r, c).value
                    if val and isinstance(val, str) and val.strip():
                        cleaned_title = re.sub(r"\s+", " ", val).strip()
                        if cleaned_title and cleaned_title not in titles:
                            titles.append(cleaned_title)

            if not titles:
                titles = [
                    "FINANCIAMIENTO CONCEDIDO POR EL BANCO CENTRAL "
                    "AL SECTOR PÚBLICO",
                    "(En miles de bolivianos)"
                ]

            metadata_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(page_number)
            }

            # Locate header row anchor
            header_row_anchor = None
            for r in range(1, 15):
                cell_val = str(ws.cell(r, 1).value or "").strip().lower()
                if re.search(r"saldos|fin\s*de", cell_val):
                    header_row_anchor = r
                    break

            if header_row_anchor is None:
                header_row_anchor = 4

            sector_row = header_row_anchor
            measure_top_row = header_row_anchor + 1
            measure_bot_row = header_row_anchor + 2

            # Map column definitions
            col_definitions = []
            for c in range(2, ws.max_column + 1):
                r_top = ws.cell(measure_top_row, c).value
                r_bot = ws.cell(measure_bot_row, c).value
                r_sec = ws.cell(sector_row, c).value

                if r_top is None and r_bot is None and r_sec is None:
                    continue

                nv2_tokens = []
                if r_top and str(r_top).strip():
                    nv2_tokens.append(str(r_top).strip())
                if r_bot and str(r_bot).strip():
                    nv2_tokens.append(str(r_bot).strip())
                nv2_str = " ".join(nv2_tokens)

                if not nv2_str:
                    continue

                col_definitions.append({
                    "col": c,
                    "raw_sector": r_sec,
                    "nv2": nv2_str
                })

            # Resolve nv1 for each 3-column group
            for i in range(0, len(col_definitions), 3):
                triplet = col_definitions[i:i + 3]
                sector_name = None
                for item in triplet:
                    raw_s = item["raw_sector"]
                    if raw_s and str(raw_s).strip():
                        clean_s = re.sub(r"\s+", " ", str(raw_s)).strip()
                        if re.sub(r"\s+", "", clean_s).upper() == "TOTAL":
                            sector_name = "TOTAL"
                        else:
                            sector_name = clean_s
                        break

                for item in triplet:
                    item["nv1"] = sector_name

            # Extract data rows starting after sub-headers
            first_data_row = header_row_anchor + 5
            records = []

            for r in range(first_data_row, ws.max_row + 1):
                date_cell = ws.cell(r, 1).value
                if date_cell is None:
                    continue

                # Stop reading at footnotes or metadata
                if isinstance(date_cell, str):
                    clean_cell_str = date_cell.strip().upper()
                    if any(
                        clean_cell_str.startswith(x)
                        for x in [
                            "FUENTE",
                            "ELABORACIÓN",
                            "ELABORACION",
                            "NOTA"
                        ]
                    ):
                        break
                    if clean_cell_str.startswith("TOTAL"):
                        continue

                # Parse date to end-of-month since report indicates "Saldos a fin de:"
                parsed_date = None
                if hasattr(date_cell, "year") and hasattr(date_cell, "month"):
                    last_day = calendar.monthrange(date_cell.year, date_cell.month)[1]
                    parsed_date = f"{date_cell.year:04d}-{date_cell.month:02d}-{last_day:02d}"
                elif isinstance(date_cell, str):
                    match_iso = re.search(
                        r"(\d{4})[-/](\d{1,2})",
                        date_cell
                    )
                    if match_iso:
                        y = int(match_iso.group(1))
                        m = int(match_iso.group(2))
                        last_day = calendar.monthrange(y, m)[1]
                        parsed_date = f"{y:04d}-{m:02d}-{last_day:02d}"

                if not parsed_date:
                    continue

                for col_info in col_definitions:
                    val = ws.cell(r, col_info["col"]).value
                    if val is not None and str(val).strip() != "":
                        try:
                            numeric_val = float(val)
                            records.append({
                                "nv1": col_info["nv1"],
                                "nv2": col_info["nv2"],
                                "fecha": parsed_date,
                                "valor": numeric_val
                            })
                        except (ValueError, TypeError):
                            pass

            df_melted = pd.DataFrame(records)
            if df_melted.empty:
                return metadata_dict, pd.DataFrame(
                    columns=["nv1", "nv2", "fecha", "valor"]
                )

            # Drop nulls and apply formatting to prevent scientific notation
            df_melted = df_melted.dropna(subset=["valor"])
            df_melted["valor"] = df_melted["valor"].apply(
                lambda x: np.format_float_positional(x, trim="-")
                if pd.notna(x) else x
            )

            # Ensure all non-value columns are string
            for col in df_melted.columns[:-1]:
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
        Validates mathematical integrity of extracted financing data:
        1. Horizontal consistency: Crédito Neto == Crédito Bruto - Depósitos
           for each sector and date.
        2. Vertical consistency: TOTAL == sum of the 4 individual sectors
           for each metric and date.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Normalized melted DataFrame or final DataFrame with metadata.
        decimal_separator : str
            Decimal separator character (default: ',').
        TOLERANCE : float
            Maximum acceptable discrepancy (default: 6.0).

        Returns
        -------
        bool
            False if validations pass, True if discrepancies exceed TOLERANCE.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if (
                "valor" not in dataframe.columns
                or "fecha" not in dataframe.columns
            ):
                return True

            df = dataframe.copy()
            df["valor_num"] = pd.to_numeric(df["valor"], errors="coerce")
            if df["valor_num"].isna().all():
                try:
                    df["valor_num"] = to_numeric_datax(
                        df["valor"], decimal_separator
                    )
                except Exception:
                    import traceback; traceback.print_exc()
                    pass

            df = df.dropna(subset=["valor_num"])

            # 1. Horizontal consistency: c = a - b for each sector and date
            piv_horiz = df.pivot_table(
                index=["fecha", "nv1"],
                columns="nv2",
                values="valor_num",
                aggfunc="first"
            ).fillna(0.0)

            needed_cols = {"Crédito Bruto", "Depósitos", "Crédito Neto"}
            if needed_cols.issubset(set(piv_horiz.columns)):
                calc_neto = (
                    piv_horiz["Crédito Bruto"] - piv_horiz["Depósitos"]
                )
                diff_horiz = (calc_neto - piv_horiz["Crédito Neto"]).abs()
                max_diff_h = diff_horiz.max()
                if max_diff_h > TOLERANCE:
                    print(
                        f"Validation failure in horizontal check (c = a - b). "
                        f"Max diff: {max_diff_h}"
                    )
                    return True

            # 2. Vertical consistency: TOTAL == sum of individual sectors
            piv_vert = df.pivot_table(
                index=["fecha", "nv2"],
                columns="nv1",
                values="valor_num",
                aggfunc="first"
            ).fillna(0.0)

            if "TOTAL" in piv_vert.columns:
                sub_sectors = [c for c in piv_vert.columns if c != "TOTAL"]
                calc_total = piv_vert[sub_sectors].sum(axis=1)
                diff_vert = (calc_total - piv_vert["TOTAL"]).abs()
                max_diff_v = diff_vert.max()
                if max_diff_v > TOLERANCE:
                    print(
                        "Validation failure in vertical check "
                        f"(TOTAL == sum). Max diff: {max_diff_v}"
                    )
                    return True

            return False

        except Exception as error:
            print(f"Validation exception occurred: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000126_01 = D_BO_000000126_01
Robot = D_BO_000000126_01
