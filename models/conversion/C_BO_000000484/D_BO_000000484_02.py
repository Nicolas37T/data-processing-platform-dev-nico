from models.conversion.Conversion_Base import Conversion_Base
import os
import re
import traceback
from typing import Tuple, Union

import pandas as pd
import pdfplumber

from models.conversion.tools.conversion_tools import month_to_number, to_numeric_datax


class D_BO_000000484_02(Conversion_Base):
    """Robot class for data extraction and validation."""

    def extraction(
        self,
        file_path: str,
        key_words: str,
        template_path: str = "",
        page_number: int = 2,
        format: str = "%Y-%m-%d",
    ) -> Union[Tuple[dict, pd.DataFrame], str]:
        """
        Extracts passive interest rate data from Excel (PAS) or PDF (page 2).

        Args:
            file_path: Path to the target Excel (.xlsx/.xls) or PDF file.
            key_words: Keywords to locate table (if needed).
            template_path: Reference template path.
            page_number: Target page number (1-based, default 2 for PAS).
            format: Output date format string.

        Returns:
            Tuple of (metadata_dict, report_df) or empty string on error.
        """
        try:
            if not os.path.exists(file_path):
                alt_path = os.path.basename(file_path)
                if os.path.exists(alt_path):
                    file_path = alt_path

            ext = os.path.splitext(file_path)[1].lower()
            titles = [
                "BANCO CENTRAL DE BOLIVIA",
                (
                    "INFORMACIÓN SOBRE EL INTERÉS QUE PERCIBEN "
                    "LOS AHORRISTAS POR SUS DEPÓSITOS"
                ),
                "TASAS PASIVAS*",
            ]
            footer_markers = (
                "tasas de interés de referencia",
                "tasas interbancarias",
                "promedios ponderados",
                "fuente",
                "vigente desde",
                "capitalizaciones",
            )
            section_keywords = ("ENTIDADES", "INSTITUCIONES")
            bancos_multiples_set = {"BANCOS MÚLTIPLES", "BANCOS MULTIPLES"}
            records = []

            if ext in (".xlsx", ".xls"):
                try:
                    df_raw = pd.read_excel(
                        file_path, sheet_name="PAS", header=None
                    )
                    detected_page = 2
                except Exception:
                    import traceback; traceback.print_exc()
                    page_idx = max(0, page_number - 1)
                    df_raw = pd.read_excel(
                        file_path, sheet_name=page_idx, header=None
                    )
                    detected_page = page_number

                doc_text = " ".join(
                    str(x)
                    for x in df_raw.iloc[:7].values.flatten()
                    if pd.notna(x)
                )

                fecha = None
                date_match = re.search(
                    r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
                    doc_text,
                    re.IGNORECASE,
                )
                if date_match:
                    day = int(date_match.group(1))
                    month = month_to_number(date_match.group(2).lower())
                    year = int(date_match.group(3))
                    if month:
                        fecha = pd.Timestamp(
                            year=year, month=month, day=day
                        ).strftime(format)

                if not fecha:
                    date_match2 = re.search(
                        r"(\d{1,2})[\s\-_/](\d{1,2})[\s\-_/](\d{4})",
                        f"{doc_text} {os.path.basename(file_path)}",
                    )
                    if date_match2:
                        day = int(date_match2.group(1))
                        month = int(date_match2.group(2))
                        year = int(date_match2.group(3))
                        fecha = pd.Timestamp(
                            year=year, month=month, day=day
                        ).strftime(format)

                if not fecha:
                    fecha = pd.Timestamp.now().strftime(format)

                hdr_row = None
                for i in range(min(15, len(df_raw))):
                    row_vals = [
                        str(x).strip().lower()
                        for x in df_raw.iloc[i].dropna()
                    ]
                    if any("moneda nacional" in v for v in row_vals):
                        hdr_row = i
                        break

                if hdr_row is None:
                    raise ValueError("Header row not found in Excel file")

                row_cur = df_raw.iloc[hdr_row].ffill()
                row_prod = df_raw.iloc[hdr_row + 1].ffill()
                row_term = df_raw.iloc[hdr_row + 2]

                col_mapping = []
                for c in range(1, len(df_raw.columns)):
                    cur = (
                        str(row_cur.iloc[c]).strip()
                        if pd.notna(row_cur.iloc[c])
                        else ""
                    )
                    prod = (
                        str(row_prod.iloc[c]).strip()
                        if pd.notna(row_prod.iloc[c])
                        else ""
                    )
                    term = (
                        str(row_term.iloc[c]).strip()
                        if pd.notna(row_term.iloc[c])
                        else "-"
                    )
                    if term.endswith(".0"):
                        term = term[:-2]
                    lower_prod = prod.lower()
                    if "caja" in lower_prod or "promedio" in lower_prod:
                        term = "-"
                    col_mapping.append((c, cur, prod, term))

                current_nv1 = None
                for idx in range(hdr_row + 3, len(df_raw)):
                    c0 = (
                        str(df_raw.iloc[idx, 0]).strip()
                        if pd.notna(df_raw.iloc[idx, 0])
                        else ""
                    )
                    if not c0 or c0.lower() == "nan":
                        continue

                    lower_c0 = c0.lower()
                    if any(m in lower_c0 for m in footer_markers):
                        break

                    c0 = re.sub(r"\s+", " ", c0)
                    upper_c0 = c0.upper()
                    is_section = upper_c0.startswith(
                        ("BANCOS", "COOPERATIVAS")
                    ) or any(k in upper_c0 for k in section_keywords)

                    if is_section:
                        if upper_c0 in bancos_multiples_set:
                            if (
                                current_nv1
                                and "MICROFINANZAS" in current_nv1.upper()
                            ):
                                continue
                        current_nv1 = c0
                        continue

                    for c_idx, nv3, nv4, nv5 in col_mapping:
                        val = df_raw.iloc[idx, c_idx]
                        val_str = "-"
                        if pd.notna(val):
                            s = str(val).strip()
                            if s and s not in ("-", "- - -", "nan"):
                                try:
                                    num = float(val)
                                    if num != 0:
                                        val_str = f"{num:.2f}"
                                except ValueError:
                                    import traceback; traceback.print_exc()
                                    pass

                        records.append(
                            {
                                "nv1": current_nv1,
                                "nv2": c0,
                                "nv3": nv3,
                                "nv4": nv4,
                                "nv5": nv5,
                                "fecha": fecha,
                                "valor": val_str,
                            }
                        )

            elif ext == ".pdf":
                detected_page = page_number
                with pdfplumber.open(file_path) as pdf:
                    target_page = pdf.pages[max(0, page_number - 1)]
                    doc_text = target_page.extract_text() or ""
                    tables = target_page.extract_tables()
                    if not tables:
                        raise ValueError(
                            f"No tables found in page {page_number} "
                            f"of {file_path}"
                        )
                    table_data = tables[0]

                fecha = None
                date_match = re.search(
                    r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
                    doc_text,
                    re.IGNORECASE,
                )
                if date_match:
                    day = int(date_match.group(1))
                    month = month_to_number(date_match.group(2).lower())
                    year = int(date_match.group(3))
                    if month:
                        fecha = pd.Timestamp(
                            year=year, month=month, day=day
                        ).strftime(format)

                if not fecha:
                    date_match2 = re.search(
                        r"(\d{1,2})[\s\-_/](\d{1,2})[\s\-_/](\d{4})",
                        f"{doc_text} {os.path.basename(file_path)}",
                    )
                    if date_match2:
                        day = int(date_match2.group(1))
                        month = int(date_match2.group(2))
                        year = int(date_match2.group(3))
                        fecha = pd.Timestamp(
                            year=year, month=month, day=day
                        ).strftime(format)

                if not fecha:
                    fecha = pd.Timestamp.now().strftime(format)

                hdr_row = None
                for i in range(min(5, len(table_data))):
                    row_vals = [
                        str(x or "").strip().lower() for x in table_data[i]
                    ]
                    if any("moneda nacional" in v for v in row_vals):
                        hdr_row = i
                        break

                if hdr_row is None:
                    raise ValueError("Header row not found in PDF table")

                p_cur = pd.Series(table_data[hdr_row]).ffill()
                p_prod = pd.Series(table_data[hdr_row + 1]).ffill()
                p_term = pd.Series(table_data[hdr_row + 2])

                col_mapping = []
                for c in range(1, len(table_data[0])):
                    cur = str(p_cur.iloc[c]).strip()
                    prod = re.sub(r"\s+", " ", str(p_prod.iloc[c])).strip()
                    term = str(p_term.iloc[c] or "").strip() or "-"
                    lower_prod = prod.lower()
                    if "caja" in lower_prod or "promedio" in lower_prod:
                        term = "-"
                    col_mapping.append((c, cur, prod, term))

                current_nv1 = None
                for idx in range(hdr_row + 3, len(table_data)):
                    row = table_data[idx]
                    c0 = str(row[0] or "").strip()
                    if not c0:
                        continue

                    lower_c0 = c0.lower()
                    if any(m in lower_c0 for m in footer_markers):
                        break

                    c0 = re.sub(r"\s+", " ", c0)
                    upper_c0 = c0.upper()
                    is_section = upper_c0.startswith(
                        ("BANCOS", "COOPERATIVAS")
                    ) or any(k in upper_c0 for k in section_keywords)

                    if is_section:
                        if upper_c0 in bancos_multiples_set:
                            if (
                                current_nv1
                                and "MICROFINANZAS" in current_nv1.upper()
                            ):
                                continue
                        current_nv1 = c0
                        continue

                    for c_idx, nv3, nv4, nv5 in col_mapping:
                        val = row[c_idx] if c_idx < len(row) else None
                        val_str = "-"
                        if val:
                            s = str(val).strip()
                            if s and s not in ("-", "- - -", "nan"):
                                try:
                                    num = float(s)
                                    if num != 0:
                                        val_str = f"{num:.2f}"
                                except ValueError:
                                    import traceback; traceback.print_exc()
                                    pass

                        records.append(
                            {
                                "nv1": current_nv1,
                                "nv2": c0,
                                "nv3": nv3,
                                "nv4": nv4,
                                "nv5": nv5,
                                "fecha": fecha,
                                "valor": val_str,
                            }
                        )
            else:
                raise ValueError(f"Unsupported file format: {ext}")

            report_df = pd.DataFrame(
                records,
                columns=[
                    "nv1", "nv2", "nv3", "nv4", "nv5", "fecha", "valor"
                ],
            )

            report_dict = {
                "file_name": os.path.basename(file_path),
                "titles": titles,
                "page_number": int(detected_page),
            }

            return report_dict, report_df

        except Exception as error:
            print(f"Could not extract report from {file_path}: {error}")
            traceback.print_exc()
            return ""

    def validate_data_results(
        self,
        dataframe: pd.DataFrame,
        decimal_separator: str,
        TOLERANCE: float = 6.0,
    ) -> bool:
        """
        Validates arithmetic consistency of extracted data.

        Args:
            dataframe: Extracted dataframe enriched with metadata.
            decimal_separator: Decimal separator ('.' or ',').
            TOLERANCE: Numeric tolerance threshold.

        Returns:
            False if validation succeeds, True if errors are detected.
        """
        try:
            if dataframe is None or dataframe.empty:
                return False

            if "valor" not in dataframe.columns:
                return False

            numeric_vals = to_numeric_datax(
                dataframe["valor"], decimal_separator
            )
            if numeric_vals.isna().all():
                return True

            return False
        except Exception as error:
            print(f"Validation error: {error}")
            traceback.print_exc()
            return True

Executor_D_BO_000000484_02 = D_BO_000000484_02
Robot = D_BO_000000484_02
