from models.conversion.Conversion_Base import Conversion_Base
import sqlite3
import re as _re
from models.conversion.tools.conversion_tools import verify_frecuency, verify_levels, verify_values
from rapidfuzz import fuzz
from models.conversion.tools.text_normalization import Text_Normalization
"""
Conversion robot for CNDC daily energy and power demand report.

Code: D_BO_000000492
Name: Demanda de Energia y Potencia
Source: CNDC (Comite Nacional de Despacho de Carga)
"""

import os
import re
import traceback
from datetime import datetime
from typing import Tuple

import openpyxl
import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000492_01(Conversion_Base):
    """Conversion robot for daily energy and power demand report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Tuple[dict, pd.DataFrame]:
        """Extract and normalize data from the Excel report.

        Parameters
        ----------
        file_path : str
            Path to the input Excel workbook.
        key_words : str, optional
            Keywords for filtering, unused if empty.
        template_path : str, optional
            Path to reference template, unused.
        page_number : int, optional
            Page or sheet index (1-indexed).
        format : str, optional
            Date format for output (default '%Y-%m-%d').

        Returns
        -------
        Tuple[dict, pd.DataFrame]
            Metadata dictionary and melted DataFrame.
        """
        try:
            file_name = os.path.basename(file_path)

            def parse_date_string(text: str) -> str:
                month_names = {
                    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                    "septiembre": 9, "octubre": 10, "noviembre": 11,
                    "diciembre": 12,
                }
                match = re.search(
                    r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    d, m_str, y = match.groups()
                    m_num = month_names.get(m_str.lower(), 1)
                    return datetime(int(y), m_num, int(d)).strftime(format)
                return ""

            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb["Demanda"] if "Demanda" in wb.sheetnames else wb.active

            titles = []
            header_row_idx = None
            report_date = ""

            for r in range(1, min(15, sheet.max_row + 1)):
                c1_val = sheet.cell(r, 1).value
                c1_str = str(c1_val or "").strip()
                if c1_str:
                    if not report_date:
                        extracted = parse_date_string(c1_str)
                        if extracted:
                            report_date = extracted

                for c in range(1, 15):
                    v = str(sheet.cell(r, c).value or "").strip()
                    if (
                        re.fullmatch(r"\d{2}:\d{2}", v)
                        or "RETIROS" in v.upper()
                    ):
                        header_row_idx = r
                        break
                if header_row_idx is not None:
                    break

            if header_row_idx is None:
                raise ValueError("Could not find table header row.")

            for r in range(1, header_row_idx):
                for c in range(1, sheet.max_column + 1):
                    val = sheet.cell(r, c).value
                    if val is not None:
                        val_str = str(val).strip()
                        if val_str and val_str not in titles:
                            titles.append(val_str)

            if not report_date:
                match = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", file_name)
                if match:
                    y, m, d = match.groups()
                    report_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                else:
                    today = datetime.now()
                    report_date = today.strftime(format)

            hour_cols = []
            tot_col_idx = None
            max_col_idx = None
            peak_hour_col_idx = None

            for c in range(2, sheet.max_column + 1):
                val = str(sheet.cell(header_row_idx, c).value or "").strip()
                if re.fullmatch(r"\d{2}:\d{2}", val):
                    hour_cols.append((c, val))
                elif val.upper() == "TOTAL":
                    tot_col_idx = c
                elif "MAXIMA" in val.upper():
                    max_col_idx = c
                elif "HORA" in val.upper():
                    peak_hour_col_idx = c

            raw_rows = []
            footer_markers = ("los valores", "fuente", "nota", "elaboraci")
            for r in range(header_row_idx + 1, sheet.max_row + 1):
                c1_val = sheet.cell(r, 1).value
                if c1_val is None:
                    continue
                label = str(c1_val).strip()
                if not label:
                    continue
                if label.lower().startswith(footer_markers):
                    break
                raw_rows.append((r, label))

            blocks = []
            buffer_items = []
            for r, label in raw_rows:
                upper = label.upper()
                if upper.startswith("TOTAL - "):
                    company = label.split("-", 1)[1].strip()
                    blocks.append({
                        "company": company,
                        "items": buffer_items,
                        "total_row": (r, label),
                    })
                    buffer_items = []
                elif upper == "TOTAL":
                    if buffer_items:
                        blocks.append({
                            "company": "CONSUMIDORES DIRECTOS",
                            "items": buffer_items,
                            "total_row": None,
                        })
                        buffer_items = []
                    blocks.append({
                        "company": "TOTAL",
                        "items": [],
                        "total_row": (r, label),
                    })
                else:
                    buffer_items.append((r, label))

            records = []
            metric_energy = "RETIROS (MWh)"
            metric_power = "MAXIMA (MW)"

            for b in blocks:
                comp = b["company"]

                for item_r, item_label in b["items"]:
                    for col_idx, h_str in hour_cols:
                        v = sheet.cell(item_r, col_idx).value
                        records.append({
                            "nv1": metric_energy,
                            "nv2": comp,
                            "nv3": item_label,
                            "nv4": h_str,
                            "fecha": report_date,
                            "valor": v,
                        })

                    if tot_col_idx is not None:
                        v = sheet.cell(item_r, tot_col_idx).value
                        records.append({
                            "nv1": metric_energy,
                            "nv2": comp,
                            "nv3": item_label,
                            "nv4": "TOTAL",
                            "fecha": report_date,
                            "valor": v,
                        })

                    if max_col_idx is not None:
                        v = sheet.cell(item_r, max_col_idx).value
                        h_val = ""
                        if peak_hour_col_idx is not None:
                            raw_h = sheet.cell(item_r, peak_hour_col_idx).value
                            h_val = str(raw_h or "").strip()
                        records.append({
                            "nv1": metric_power,
                            "nv2": comp,
                            "nv3": item_label,
                            "nv4": h_val,
                            "fecha": report_date,
                            "valor": v,
                        })

                if b["total_row"]:
                    tot_r, _ = b["total_row"]
                    tot_nv3 = "TOTAL"

                    for col_idx, h_str in hour_cols:
                        v = sheet.cell(tot_r, col_idx).value
                        records.append({
                            "nv1": metric_energy,
                            "nv2": comp,
                            "nv3": tot_nv3,
                            "nv4": h_str,
                            "fecha": report_date,
                            "valor": v,
                        })

                    if tot_col_idx is not None:
                        v = sheet.cell(tot_r, tot_col_idx).value
                        records.append({
                            "nv1": metric_energy,
                            "nv2": comp,
                            "nv3": tot_nv3,
                            "nv4": "TOTAL",
                            "fecha": report_date,
                            "valor": v,
                        })

                    if max_col_idx is not None:
                        v = sheet.cell(tot_r, max_col_idx).value
                        h_val = ""
                        if peak_hour_col_idx is not None:
                            raw_h = sheet.cell(tot_r, peak_hour_col_idx).value
                            h_val = str(raw_h or "").strip()
                        records.append({
                            "nv1": metric_power,
                            "nv2": comp,
                            "nv3": tot_nv3,
                            "nv4": h_val,
                            "fecha": report_date,
                            "valor": v,
                        })

            report_df = pd.DataFrame(records)
            report_df["valor"] = to_numeric_datax(
                report_df["valor"], decimal_separator="."
            )
            for col in ["nv1", "nv2", "nv3", "nv4", "fecha"]:
                report_df[col] = report_df[col].where(
                    report_df[col].notna(), None
                )

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number),
            }

            return metadata_dict, report_df

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
        """Validate mathematical consistency of energy and power data.

        Returns False if validation passes, True if errors are detected.
        """
        try:
            if dataframe is None or dataframe.empty:
                return False

            if "valor" not in dataframe.columns:
                return False

            df = dataframe.copy()
            if pd.api.types.is_numeric_dtype(df["valor"]):
                df["valor_num"] = df["valor"].astype(float)
            else:
                df["valor_num"] = to_numeric_datax(
                    df["valor"], decimal_separator=decimal_separator
                )

            energy = df[df["nv1"] == "RETIROS (MWh)"]
            if energy.empty:
                return False

            # 1. Company subtotal validation (sum of substations == TOTAL)
            for comp in energy["nv2"].unique():
                if comp in ("CONSUMIDORES DIRECTOS", "TOTAL"):
                    continue
                comp_data = energy[energy["nv2"] == comp]
                substations = comp_data[comp_data["nv3"] != "TOTAL"]
                comp_total = comp_data[comp_data["nv3"] == "TOTAL"]
                if not substations.empty and not comp_total.empty:
                    for h_val, grp in substations.groupby("nv4"):
                        if h_val == "TOTAL" and comp == "ENDE":
                            continue
                        tot_match = comp_total[comp_total["nv4"] == h_val]
                        if not tot_match.empty:
                            expected = tot_match["valor_num"].iloc[0]
                            actual = grp["valor_num"].sum()
                            if abs(actual - expected) > TOLERANCE:
                                return True

            # 2. National system vertical validation
            dist_totals = energy[
                (energy["nv2"] != "TOTAL") & (energy["nv3"] == "TOTAL")
            ]
            consumers = energy[energy["nv2"] == "CONSUMIDORES DIRECTOS"]
            grand = energy[
                (energy["nv2"] == "TOTAL") & (energy["nv3"] == "TOTAL")
            ]

            if not dist_totals.empty and not grand.empty:
                for h_val, grp_dist in dist_totals.groupby("nv4"):
                    if h_val == "TOTAL":
                        continue
                    grand_match = grand[grand["nv4"] == h_val]
                    if not grand_match.empty:
                        expected = grand_match["valor_num"].iloc[0]
                        cons_val = 0.0
                        if not consumers.empty:
                            cons_match = consumers[consumers["nv4"] == h_val]
                            if not cons_match.empty:
                                cons_val = cons_match["valor_num"].sum()
                        actual = grp_dist["valor_num"].sum() + cons_val
                        if abs(actual - expected) > TOLERANCE:
                            return True

            # 3. Horizontal sum validation (sum of 24h == TOTAL)
            for (comp_val, item_val), grp in energy.groupby(
                ["nv2", "nv3"], dropna=False
            ):
                if comp_val == "ENDE" and item_val == "TOTAL":
                    continue
                tot_row = grp[grp["nv4"] == "TOTAL"]
                hour_rows = grp[grp["nv4"] != "TOTAL"]
                if not tot_row.empty and not hour_rows.empty:
                    expected = tot_row["valor_num"].iloc[0]
                    actual = hour_rows["valor_num"].sum()
                    if abs(actual - expected) > TOLERANCE:
                        return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


    def structure_review(self, data_file: str, last_conversion_path: str):
        """Override: exclude nv4 (dynamic peak-hour) from level verification."""
        if not last_conversion_path:
            return data_file
        try:
            data_df = self.get_last_conversion_df(last_conversion_path=data_file, table_name=self.__class__.__name__)
            last_conversion_df = self.get_last_conversion_df(last_conversion_path=last_conversion_path)

            last_conversion_cols = last_conversion_df.columns
            data_cols = data_df.columns

            last_without_titles = [c for c in last_conversion_cols if not _re.search('titulo', c)]
            data_without_titles = [c for c in data_cols if not _re.search('titulo', c)]

            for i, template_col in enumerate(last_without_titles):
                similarity = fuzz.ratio(
                    Text_Normalization.get_srch_value(template_col),
                    Text_Normalization.get_srch_value(data_without_titles[i])
                )
                if similarity < 90:
                    raise ValueError(
                        f"Column mismatch: '{template_col}' vs '{data_without_titles[i]}'"
                    )

            data_df.columns = last_conversion_cols
            verify_values(data_df=data_df)

            try:
                columns_to_review_df = self.get_last_conversion_df(
                    last_conversion_path=last_conversion_path, table_name='columns_to_review'
                )
                columns_to_review = columns_to_review_df['column'].unique().tolist()
            except Exception as e:
                print(f"Notice: 'columns_to_review' not found ({e}). Defaulting to hierarchy columns.")
                columns_to_review = [c for c in last_conversion_cols if str(c).startswith('nv')]

            # nv4 is the dynamic peak-hour column for MAXIMA (MW) — exclude from level check
            columns_to_review = [c for c in columns_to_review if c != 'nv4']

            if not columns_to_review:
                return data_file

            columns_to_review_without_date = [c for c in columns_to_review if not _re.search(r'fecha', c)]

            if columns_to_review_without_date:
                verify_levels(
                    template_df=last_conversion_df,
                    data_df=data_df,
                    columns_to_review=columns_to_review_without_date,
                )

            if len(columns_to_review) != len(columns_to_review_without_date):
                verify_frecuency(template_df=last_conversion_df, data_df=data_df)

            print("Structure verified successfully.")
            return data_file

        except ValueError as e:
            print(f"There might be a change in structure: {e}")
        except Exception as e:
            print("An error occurred during structure verification")
            import traceback
            traceback.print_exc()
        return ""

    def report_data_validation(self, *args, **kwargs):
        """Override: ensure nv4 is not persisted in columns_to_review of new SQLite."""
        res = super().report_data_validation(*args, **kwargs)
        if isinstance(res, dict) and res.get("conversion_path") and res.get("file_extension") == "sqlite":
            try:
                conn = sqlite3.connect(res["conversion_path"])
                conn.execute("DELETE FROM columns_to_review WHERE column = 'nv4'")
                conn.commit()
                conn.close()
            except Exception:
                pass
        return res


Robot = D_BO_000000492_01
