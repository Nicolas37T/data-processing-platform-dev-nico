from models.conversion.Conversion_Base import Conversion_Base
# -*- coding: utf-8 -*-
"""Conversion robot for report D_BO_000000289_01.

Report: "Reclamos Recibidos en Segunda Instancia por Tipo de Entidad" (ASFI).
Source: monthly ``.xls`` sheet with one row per financial entity, one column
per month (Enero..Diciembre) plus a printed ``Total`` and a ``%`` column.

The robot flattens the double-entry table into the DATAX vertical (melted)
format ``[nv1, nv2, nv3, nv4, fecha, valor]`` and reconciles the printed
monthly totals against the calculated sums.
"""

import os
import re
import calendar
import traceback

import pandas as pd

from models.conversion.tools.conversion_tools import to_numeric_datax
from models.download.tools.download_tools import month_to_number


class D_BO_000000289_01(Conversion_Base):
    """Conversion robot for the ASFI second-instance complaints report."""

    def extraction(
        self,
        file_path: str,
        key_words: str = "",
        template_path: str = "",
        page_number: int = 1,
        format: str = "%Y-%m-%d",
    ) -> tuple:
        """Extract and flatten the complaints table into melted format.

        Args:
            file_path: Absolute path to the downloaded ``.xls`` source file.
            key_words: Keywords used to identify the table (unused here, the
                report has a single sheet).
            template_path: Reference template path (not required).
            page_number: 1-based sheet index where the table starts.
            format: Expected output date format (``%Y-%m-%d``).

        Returns:
            A ``(metadata_dict, dataframe)`` tuple, or an empty string ``""``
            if an unrecoverable error occurs.
        """
        try:
            file_name = os.path.basename(file_path)

            # 1. Resolve the temporal cut dynamically from the file name.
            cut_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", file_name)
            if cut_match:
                cut_year = int(cut_match.group(1))
                cut_month = int(cut_match.group(2))
                cut_day = int(cut_match.group(3))
            else:
                # Fallback for names formatted as YYYYMM (no separators).
                cut_match = re.search(r"(\d{4})(\d{2})", file_name)
                cut_year = int(cut_match.group(1))
                cut_month = int(cut_match.group(2))
                cut_day = calendar.monthrange(cut_year, cut_month)[1]
            cut_date = f"{cut_year:04d}-{cut_month:02d}-{cut_day:02d}"

            # 2. Load the target sheet (raw, without header inference).
            sheet_index = max(int(page_number) - 1, 0)
            sheet = pd.read_excel(file_path, sheet_name=sheet_index, header=None)

            # Nested helper: normalize any cell into a single-spaced string.
            def clean_text(value) -> str:
                return re.sub(r"\s+", " ", str(value)).strip()

            # 3. Locate the header row (the one holding the month names).
            header_row = None
            for r in range(len(sheet)):
                labels = [clean_text(v).lower() for v in sheet.iloc[r].tolist() if pd.notna(v)]
                month_hits = sum(1 for lab in labels if month_to_number(lab))
                if month_hits >= 3:
                    header_row = r
                    break
            if header_row is None:
                raise ValueError("Header row with month columns not found.")

            # Master concept (nv1) is the label of the first column header.
            master_concept = clean_text(sheet.iloc[header_row, 0])

            # 4. Build the report titles from the lines above the header.
            titles = []
            for r in range(header_row):
                cell = sheet.iloc[r, 0]
                if pd.notna(cell):
                    text = clean_text(cell)
                    if text:
                        titles.append(text)

            # 5. Map each data column to its melted label and resolved date.
            #    Months after the cut month (all zeros) are skipped.
            columns_meta = {}
            for col in range(1, sheet.shape[1]):
                raw_label = sheet.iloc[header_row, col]
                if pd.isna(raw_label):
                    continue
                label = clean_text(raw_label)
                month_num = month_to_number(label.lower())
                if month_num:
                    if month_num > cut_month:
                        continue
                    last_day = calendar.monthrange(cut_year, month_num)[1]
                    resolved = f"{cut_year:04d}-{month_num:02d}-{last_day:02d}"
                    columns_meta[col] = {"label": label, "fecha": resolved, "is_pct": False}
                elif label.lower() == "total":
                    columns_meta[col] = {"label": label, "fecha": cut_date, "is_pct": False}
                elif "%" in label:
                    columns_meta[col] = {"label": "Porcentaje", "fecha": cut_date, "is_pct": True}

            # 6. Walk the body rows, tracking the current sector for nv2.
            records = []
            current_sector = None

            for r in range(header_row + 1, len(sheet)):
                raw_label = sheet.iloc[r, 0]
                if pd.isna(raw_label):
                    continue
                label = clean_text(raw_label)
                if not label:
                    continue

                has_data = sheet.iloc[r, 1:].notna().any()
                label_upper = label.upper()

                # Sector header: text with no numeric data -> defines nv2.
                if not has_data:
                    current_sector = label
                    continue

                # Determine the hierarchy for the current data row.
                if label_upper.startswith(("SUB-TOTAL", "SUBTOTAL")):
                    nv2, nv3 = current_sector, "SUB-TOTAL"
                elif label_upper.startswith("TOTAL"):
                    nv2, nv3 = "TOTALES", None
                else:
                    nv2, nv3 = current_sector, label

                # Un-pivot every mapped column into a melted record.
                for col, meta in columns_meta.items():
                    cell = sheet.iloc[r, col]
                    if pd.isna(cell):
                        continue
                    if meta["is_pct"]:
                        value = round(float(cell) * 100, 2)
                    else:
                        value = int(round(float(cell)))
                    records.append({
                        "nv1": master_concept,
                        "nv2": nv2,
                        "nv3": nv3,
                        "nv4": meta["label"],
                        "fecha": meta["fecha"],
                        "valor": value,
                    })

            dataframe = pd.DataFrame(records, columns=["nv1", "nv2", "nv3", "nv4", "fecha", "valor"])

            # 7. Normalize the numeric column with the local platform helper.
            dataframe["valor"] = to_numeric_datax(dataframe["valor"], decimal_separator=".")

            metadata_dict = {
                "file_name": file_name,
                "titles": titles,
                "page_number": int(page_number),
            }

            return metadata_dict, dataframe

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str = ",",
        TOLERANCE: float = 6.0,
    ) -> bool:
        """Reconcile printed row totals against the calculated monthly sums.

        For every entity the sum of its monthly values must match the printed
        ``Total`` value within ``TOLERANCE``.

        Args:
            dataframe: Melted DataFrame returned by ``extraction()``.
            decimal_separator: Decimal separator configured for the report.
            TOLERANCE: Allowed rounding difference.

        Returns:
            ``False`` when the data is consistent (or there is nothing to
            reconcile); ``True`` when a discrepancy larger than ``TOLERANCE``
            is found.
        """
        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return False
            required = {"nv2", "nv3", "nv4", "valor"}
            if not required.issubset(dataframe.columns):
                return False

            month_names = {
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "setiembre", "octubre",
                "noviembre", "diciembre",
            }

            df = dataframe.copy()
            df["_value"] = to_numeric_datax(df["valor"], decimal_separator)
            df["_level"] = df["nv4"].astype(str).str.strip().str.lower()

            # One group per entity (nv2 + nv3), keeping the grand-total group.
            entity_key = df["nv2"].astype(str) + "||" + df["nv3"].astype(str)

            for _, group in df.groupby(entity_key):
                total_rows = group.loc[group["_level"] == "total"]
                if total_rows.empty:
                    continue
                printed_total = total_rows["_value"].iloc[0]
                monthly_sum = group.loc[group["_level"].isin(month_names), "_value"].sum()
                if abs(monthly_sum - printed_total) > TOLERANCE:
                    return True

            return False

        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True


# Alias so the repository test harness (``from robot import Robot``) works
# while the class keeps the mandatory report-code name for the V2 platform.
Robot = D_BO_000000289_01

Executor_D_BO_000000289_01 = D_BO_000000289_01
Robot = D_BO_000000289_01
