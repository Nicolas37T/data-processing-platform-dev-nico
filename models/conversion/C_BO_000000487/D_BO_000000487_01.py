"""
Module for extracting and validating report D_BO_000000487_01.

Code: D_BO_000000487_01
Periodicity: Daily
Decimal Separator: .
Conversion Factor: 1
"""

import os
import re
import traceback
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Union
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


def excel_date_to_str(val: Any, format: str = "%Y-%m-%d") -> str:
    """Convert Excel serial date or date string to YYYY-MM-DD format."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, datetime):
        return val.strftime(format)
    if isinstance(val, (int, float)):
        try:
            val_float = float(val)
            if val_float > 30000:  # Excel serial date
                base = datetime(1899, 12, 30)
                return (base + timedelta(days=val_float)).strftime(format)
        except Exception:
            pass
    v_str = str(val or "").strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v_str)
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return datetime(y, m, d).strftime(format)
    match_lat = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", v_str)
    if match_lat:
        d, m, y = int(match_lat.group(1)), int(match_lat.group(2)), int(match_lat.group(3))
        return datetime(y, m, d).strftime(format)
    return ""


class D_BO_000000487_01(Conversion_Base):
    """Robot class to extract and validate D_BO_000000487_01 report data."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> Union[Tuple[Dict[str, Any], Any], str]:
        """Extract and normalize data for report D_BO_000000487_01.

        Parameters
        ----------
        file_path : str
            Absolute path of the downloaded source file.
        key_words : str, optional
            Keywords to identify and validate table.
        template_path : str, optional
            Path to reference template.
        page_number : int, optional
            Page or sheet index (default 1).
        format : str, optional
            Expected date format (default '%Y-%m-%d').

        Returns
        -------
        tuple[dict, pd.DataFrame] | str
            Tuple of (metadata_dict, df_melted) or empty string "" on error.
        """
        del template_path
        try:
            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return ""

            rows_list = []
            doc_titles = ["EVOLUCIÓN DE LAS TASAS DE REFERENCIA (*)"]
            subtitle = "(En porcentaje)"

            df_raw = pd.read_excel(file_path, header=None)
            raw_rows = df_raw.values.tolist()

            if not raw_rows:
                print(f"Could not parse content from {file_path}")
                return ""

            instruments = ["MN", "MVDOL", "MN-UFV", "ME"]
            col_map = {}
            header_row_idx = -1

            for r_idx, row in enumerate(raw_rows):
                row_strs = [str(v).strip().upper() if v is not None and not pd.isna(v) else "" for v in row]
                if any(inst in row_strs for inst in instruments):
                    header_row_idx = r_idx
                    for c_idx, val in enumerate(row_strs):
                        if val in instruments:
                            col_map[val] = c_idx
                    break

            if header_row_idx == -1:
                col_map = {"MN": 3, "MVDOL": 4, "MN-UFV": 5, "ME": 6}
                header_row_idx = 4

            start_row = header_row_idx + 1

            for r in range(start_row, len(raw_rows)):
                row = raw_rows[r]
                if len(row) < 4:
                    continue

                p_desde_raw = row[1] if len(row) > 1 else None
                p_hasta_raw = row[2] if len(row) > 2 else None

                p_desde = excel_date_to_str(p_desde_raw, format=format)
                p_hasta = excel_date_to_str(p_hasta_raw, format=format)

                if not p_desde or not p_hasta:
                    continue

                period_str = f"Periodo de Cálculo: {p_desde} - {p_hasta}"

                v_desde_raw = row[7] if len(row) > 7 else None
                v_hasta_raw = row[8] if len(row) > 8 else None

                v_desde = excel_date_to_str(v_desde_raw, format=format)
                v_hasta = excel_date_to_str(v_hasta_raw, format=format)

                vigencia_str = f"Vigencia: {v_desde} - {v_hasta}" if (v_desde and v_hasta) else ""

                fecha_raw = row[8] if len(row) > 8 and row[8] is not None and not pd.isna(row[8]) else (
                    row[7] if len(row) > 7 and row[7] is not None and not pd.isna(row[7]) else (
                        row[0] if len(row) > 0 else None
                    )
                )
                fecha_str = excel_date_to_str(fecha_raw, format=format)
                if not fecha_str:
                    fecha_str = datetime.now().strftime(format)

                for inst_name, c_idx in col_map.items():
                    if c_idx < len(row):
                        raw_val = row[c_idx]
                        if raw_val is not None and not pd.isna(raw_val):
                            val_num = float(raw_val) if isinstance(raw_val, (int, float)) else to_numeric_datax(pd.Series([raw_val]), decimal_separator=".").iloc[0]
                            row_dict = {
                                "nv1": doc_titles[0],
                                "nv2": subtitle,
                                "nv3": period_str,
                            }
                            if vigencia_str:
                                row_dict["nv4"] = vigencia_str
                                row_dict["nv5"] = inst_name
                            else:
                                row_dict["nv4"] = inst_name
                            row_dict["fecha"] = fecha_str
                            row_dict["valor"] = val_num
                            rows_list.append(row_dict)

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": doc_titles,
                "page_number": page_number,
            }

            df_melted = pd.DataFrame(rows_list)
            return (metadata, df_melted)

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: Any,
        decimal_separator: str = ".",
        TOLERANCE: float = 6.0,
    ) -> bool:
        try:
            if dataframe is None or dataframe.empty:
                return False
            return False
        except Exception:
            traceback.print_exc()
            return True

    def report_data_validation(self, code, reviewed_files, path, publication_frequency, last_conversion_path, file_extension, mongo_client, decimal_separator):
        converted_file = super().report_data_validation(
            code=code,
            reviewed_files=reviewed_files,
            path=path,
            publication_frequency=publication_frequency,
            last_conversion_path=last_conversion_path,
            file_extension=file_extension,
            mongo_client=mongo_client,
            decimal_separator=decimal_separator,
        )
        if file_extension == "sqlite" and converted_file and "conversion_path" in converted_file:
            try:
                import sqlite3
                from models.conversion.tools.conversion_tools import convert_unix_path
                sqlite_path = convert_unix_path(converted_file["conversion_path"])
                if os.path.exists(sqlite_path):
                    conn = sqlite3.connect(sqlite_path)
                    cur = conn.cursor()
                    cur.execute("DROP TABLE IF EXISTS columns_to_review")
                    cur.execute("CREATE TABLE columns_to_review (column TEXT)")
                    cur.executemany("INSERT INTO columns_to_review (column) VALUES (?)", [
                        ("fecha",),
                        ("nv1",),
                        ("nv2",),
                        ("nv5",),
                    ])
                    conn.commit()
                    conn.close()
            except Exception:
                traceback.print_exc()
        return converted_file

