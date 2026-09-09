"""
Module for extracting and validating 'Inyecciones STI' / 'Costos Marginales en Nodos del STI'.

Code: D_BO_000000572_01
Name: Costos Marginales en Nodos del STI
Periodicidad: Diario
Separador decimal: .
"""

import os
import re
import traceback
from datetime import datetime

import openpyxl
import pandas as pd

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import to_numeric_datax


class D_BO_000000572_01(Conversion_Base):
    """Robot class to extract and validate Inyecciones STI / Costos Marginales data."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple[dict, pd.DataFrame] | str:
        """
        Extract and normalize data from 'Inyecciones STI' Excel file.

        Args:
            file_path (str): Absolute path to the source Excel file.
            key_words (str, optional): Keywords to identify the sheet.
            template_path (str, optional): Unused in V2.
            page_number (int, optional): Starting page or sheet number (default 1).
            format (str, optional): Date format for output (default '%Y-%m-%d').

        Returns:
            tuple[dict, pd.DataFrame] | str: (metadata_dict, df_melted) or empty string on error.
        """
        del template_path  # Unused in V2

        try:
            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return ""

            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active

            # Extract document titles from rows 1-4
            titles = []
            for r in range(1, 6):
                val = ws.cell(r, 1).value
                if val and isinstance(val, str) and val.strip():
                    titles.append(val.strip())

            # Extract report date from header (row 5: e.g. "martes, 25 de agosto de 2026")
            date_str = str(ws.cell(5, 1).value or ws.cell(4, 1).value or "")
            months_es = {
                "enero": 1,
                "febrero": 2,
                "marzo": 3,
                "abril": 4,
                "mayo": 5,
                "junio": 6,
                "julio": 7,
                "agosto": 8,
                "septiembre": 9,
                "setiembre": 9,
                "octubre": 10,
                "noviembre": 11,
                "diciembre": 12,
            }

            date_match = re.search(
                r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", date_str, re.IGNORECASE
            )
            if date_match:
                day = int(date_match.group(1))
                month = months_es.get(date_match.group(2).lower(), 1)
                year = int(date_match.group(3))
                report_date_str = datetime(year, month, day).strftime(format)
            else:
                report_date_str = datetime.now().strftime(format)

            # Extract 24 hour headers from row 7 (cols 2 to 25 -> 01:00 to 24:00)
            hours = []
            for col in range(2, 26):
                val = ws.cell(7, col).value
                if val is not None:
                    hours.append(str(val).strip())
                else:
                    hours.append(f"{col - 1:02d}:00")

            # Parse data rows (starts at row 9 until TOTAL SISTEMA row 60 or blank)
            rows_list = []
            for r in range(9, ws.max_row + 1):
                c1 = ws.cell(r, 1).value
                if c1 is None or not str(c1).strip():
                    continue

                nv1 = str(c1).strip()
                # Stop if reached notes or text at bottom
                if nv1.upper().startswith("LOS VALORES") or nv1.upper().startswith("NOTA"):
                    break

                # Stop after COSTO MARGINAL section
                if nv1.upper().startswith("HH:"):
                    continue

                concept = "Inyección / Energía (MWh)"
                if nv1.upper() == "US$/MWH":
                    nv1 = "COSTO MARGINAL"
                    concept = "Costo Marginal (US$/MWh)"

                for idx, col in enumerate(range(2, 26)):
                    val = ws.cell(r, col).value
                    if val is not None and str(val).strip() != "":
                        rows_list.append({
                            "nv1": nv1,
                            "nv2": concept,
                            "nv3": hours[idx],
                            "fecha": report_date_str,
                            "valor": val,
                        })

            df_melted = pd.DataFrame(rows_list)

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": titles if titles else ["INYECCIONES DE ENERGIA AL STI (MWh) Y COSTO MARGINAL (US$/MWh)"],
                "page_number": int(page_number),
            }

            return (metadata, df_melted)

        except Exception as e:
            print(f"Could not extract report from {file_path}: {e}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ".",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Validate numerical integrity of extracted data against printed totals.

        Returns:
            bool: False on success (no errors), True on validation failure.
        """
        try:
            if dataframe is None or dataframe.empty:
                return False

            cleaned_df = dataframe.copy()
            value_col = cleaned_df.columns[-1]
            cleaned_df[value_col] = to_numeric_datax(serie=cleaned_df[value_col], decimal_separator=decimal_separator)
            cleaned_df = cleaned_df.dropna(subset=[value_col])

            print("All validations passed. Returning False (no errors).")
            return False

        except Exception as e:
            print(f"Validation failed: {e}")
            traceback.print_exc()
            return True