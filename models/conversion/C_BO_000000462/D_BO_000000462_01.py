import os
import re
import traceback
from datetime import datetime, timedelta

import pandas as pd
import pdfplumber

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import search_key_words, to_numeric_datax


class D_BO_000000462_01(Conversion_Base):

    def extraction(self, file_path, key_words='', template_path='', page_number=1, format='%Y-%m-%d', output_path=None):
        """
        Extracts data from a PDF file based on a template and keywords.
        Uses pdfplumber (pure Python, no Java/tabula dependency).
        """
        del template_path, output_path
        try:
            file_name = os.path.basename(file_path)
            print(f"Extracting data from file: {file_name} ...")
            page_number = int(page_number)

            if os.path.splitext(file_path)[1].lower() != ".pdf":
                raise ValueError(f"Unsupported file extension: {os.path.splitext(file_path)[1]}")

            with pdfplumber.open(file_path) as pdf:
                page = pdf.pages[max(page_number - 1, 0)]
                page_text = page.extract_text() or ""
                if key_words and not search_key_words(page_text, key_words):
                    raise ValueError(f"No tables found matching keywords: {key_words}")

                def clean_numeric(val):
                    if val is None:
                        return 0.0
                    val_str = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", str(val)).replace(",", ".").strip()
                    if not val_str or val_str.lower() in ("-", "--", "s/c", "s/i", "none", "nan", "null"):
                        return 0.0
                    val_clean = re.sub(r"[^\d.-]", "", val_str)
                    try:
                        return float(val_clean)
                    except ValueError:
                        return 0.0

                rows = []
                for pdf_table in page.find_tables():
                    source_table = pdf_table.extract()
                    header_index = next(
                        (index for index, row in enumerate(source_table)
                         if "MIN." in " ".join(str(value or "") for value in row).upper()
                         and "MAX." in " ".join(str(value or "") for value in row).upper()),
                        None,
                    )
                    if header_index is None:
                        continue

                    if pdf_table.bbox[1] < 160:
                        heading = "CONSUMIDOR: P/ A MANO C/MENUDO (Bs./Kg.)"
                    else:
                        heading = "CONSUMIDOR: P/ A MAQUINA C/MENUDO (Bs./Kg.)"

                    date_matches = re.findall(
                        r"\d{1,2}/\d{1,2}/\d{2,4}",
                        " ".join(str(value or "") for row in source_table[header_index:header_index + 2] for value in row),
                    )
                    if not date_matches:
                        continue
                    date_value = datetime.strptime(date_matches[0], "%d/%m/%y")
                    previous_date = (
                        datetime.strptime(date_matches[1], "%d/%m/%y")
                        if len(date_matches) > 1
                        else date_value - timedelta(days=1)
                    )
                    expected_markets = ["MUTUALISTA", "LOS POZOS", "ABASTO", "RAMADA"]
                    if heading == "CONSUMIDOR: P/ A MANO C/MENUDO (Bs./Kg.)":
                        expected_markets.append("PROMEDIO")

                    for row_index, source_row in enumerate(source_table[header_index + 1:]):
                        raw_market_str = str(source_row[0] or "").strip()
                        
                        # Handle cases where multiple markets were merged by pdfplumber
                        # e.g., 'LOS POZOS\nABASTO' or 'LOS POZOS ABASTO'
                        cell_texts = [c for c in raw_market_str.split("\n") if c.strip()]
                        if len(cell_texts) > 1:
                            sub_markets = cell_texts
                        elif re.search(r"LOS\s+POZOS.*ABASTO", raw_market_str, re.IGNORECASE):
                            sub_markets = ["LOS POZOS", "ABASTO"]
                        else:
                            sub_markets = [raw_market_str]

                        # Check if numerical columns also contain multiple newline-separated values
                        def get_col_values(idx):
                            val_raw = source_row[idx] if len(source_row) > idx else None
                            if val_raw is None:
                                return []
                            parts = str(val_raw).split("\n")
                            return [clean_numeric(p) for p in parts if p.strip()]

                        col_mins = get_col_values(1)
                        col_maxs = get_col_values(2)
                        col_cur_avgs = get_col_values(3)
                        col_prev_avgs = get_col_values(4)

                        for sub_idx, sub_market in enumerate(sub_markets):
                            market = sub_market.strip()
                            if not market and row_index < len(expected_markets):
                                market = expected_markets[row_index]

                            # Standardize market names to match historical levels exactly
                            market_upper = re.sub(r"\s+", " ", market.upper()).strip()
                            if "MUTUALISTA" in market_upper:
                                market = "MUTUALISTA"
                            elif "LOS POZOS" in market_upper:
                                market = "LOS POZOS"
                            elif "ABASTO" in market_upper:
                                market = "ABASTO"
                            elif "RAMADA" in market_upper:
                                market = "RAMADA"
                            elif "PROMEDIO" in market_upper:
                                market = "PROMEDIO"

                            cur_avg = col_cur_avgs[sub_idx] if sub_idx < len(col_cur_avgs) else (col_cur_avgs[0] if col_cur_avgs else 0.0)

                            if market == "PROMEDIO":
                                continue

                            min_val = col_mins[sub_idx] if sub_idx < len(col_mins) else (col_mins[0] if col_mins else 0.0)
                            max_val = col_maxs[sub_idx] if sub_idx < len(col_maxs) else (col_maxs[0] if col_maxs else 0.0)
                            prev_avg = col_prev_avgs[sub_idx] if sub_idx < len(col_prev_avgs) else (col_prev_avgs[0] if col_prev_avgs else 0.0)
                            daily_variation = round(cur_avg - prev_avg, 2)

                            statistics = [
                                ("MÍN.", min_val, date_value),
                                ("MÁX.", max_val, date_value),
                                ("PROM.", cur_avg, date_value),
                                ("PROM.", prev_avg, previous_date),
                                ("VAR. DIARIA", daily_variation, date_value),
                            ]

                            for statistic, value, row_date in statistics:
                                rows.append([
                                    heading, "MERCADOS", statistic, market,
                                    row_date.strftime(format), value,
                                ])

                for line in page.extract_text_lines():
                    text = re.sub(r"\s+", " ", line["text"]).strip()
                    producer_match = re.search(
                        r"(P/A\s+\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
                        text,
                        re.IGNORECASE,
                    )
                    if producer_match:
                        minimum = clean_numeric(producer_match.group(2))
                        maximum = clean_numeric(producer_match.group(3))
                        current = clean_numeric(producer_match.group(4))
                        previous = clean_numeric(producer_match.group(5))
                        producer_date = date_value
                        producer_previous_date = previous_date
                        producer_values = [
                            ("MÍN.", minimum, producer_date),
                            ("MÁX.", maximum, producer_date),
                            ("PROM.", current, producer_date),
                            ("PROM.", previous, producer_previous_date),
                            ("VAR. DIARIA", round(current - previous, 2), producer_date),
                        ]
                        for statistic, value, row_date in producer_values:
                            rows.append([
                                "PRECIO REFERENCIAL DE POLLO VIVO AL PRODUCTOR (Bs./Kg.)",
                                "TIPO DE POLLO", statistic, producer_match.group(1).upper(),
                                row_date.strftime(format), value,
                            ])

            dataframe = pd.DataFrame(rows, columns=["nv1", "nv2", "nv3", "nv4", "fecha", "valor"])
            dataframe["valor"] = dataframe["valor"].apply(clean_numeric)

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": [],
                "page_number": page_number,
            }
            return metadata, dataframe
        except Exception:
            traceback.print_exc()
            return ""

    def validate_data_results(self, dataframe, decimal_separator, TOLERANCE=6.0):
        """
        Validates the extracted data results.
        Returns False if valid, True on error.
        """
        try:
            if dataframe is None or dataframe.empty:
                print("Validation failed: DataFrame is empty.")
                return True

            required_columns = {"nv1", "nv2", "nv3", "nv4", "fecha", "valor"}
            if not required_columns.issubset(dataframe.columns):
                missing_columns = required_columns.difference(dataframe.columns)
                print(f"Validation failed: missing columns {sorted(missing_columns)}.")
                return True

            if dataframe["valor"].isna().any():
                print("Validation failed: NaN values found in 'valor' column.")
                return True

            return False
        except Exception:
            traceback.print_exc()
            return True


Robot = D_BO_000000462_01
Executor_D_BO_000000462_01 = D_BO_000000462_01
