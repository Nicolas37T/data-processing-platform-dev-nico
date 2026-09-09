import os
import re
import traceback
from datetime import datetime, timedelta

import pandas as pd
import pdfplumber

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import search_key_words


class D_BO_000000462_01(Conversion_Base):

    def extraction(self, file_path, key_words='', template_path='', page_number=1, format='%Y-%m-%d', output_path=None):
        """
        Extracts data from a PDF file based on a template and keywords.

        Parameters:
            file_path (str): Path to the PDF file.
            key_words (str): Keywords to search for in the PDF.
            template_path (str): Path to the template for extraction.
            page_number (int): Page number to extract data from.
            format (str, optional): Date format for extracted dates. Defaults to '%Y-%m-%d'.
            output_path (str, optional): Path for the extracted Excel file. Defaults
                to the PDF path with an '_extracted.xlsx' suffix.
        Returns:
            A tuple containing the extracted data and the date of the file.
            (metadatos_dict, df_melted)
        """
        del template_path, output_path
        try:
            file_name = file_path.split("/")[-1]
            print(f"Extracting data from file: {file_name} ...")
            page_number = int(page_number)

            if os.path.splitext(file_path)[1].lower() != ".pdf":
                raise ValueError(f"Unsupported file extension: {os.path.splitext(file_path)[1]}")

            with pdfplumber.open(file_path) as pdf:
                page = pdf.pages[max(page_number - 1, 0)]
                page_text = page.extract_text() or ""
                if key_words and not search_key_words(page_text, key_words):
                    raise ValueError(f"No tables found matching keywords: {key_words}")

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
                    header = source_table[header_index]
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
                        market = str(source_row[0] or "").strip()
                        if not market:
                            if row_index < len(expected_markets):
                                market = expected_markets[row_index]
                            else:
                                market = "PROMEDIO"
                        if market.upper().startswith("PROMEDIO"):
                            market = "PROMEDIO"
                        statistics = [
                            ("MÍN.", source_row[1], date_value),
                            ("MÁX.", source_row[2], date_value),
                            ("PROM.", source_row[3], date_value),
                            ("PROM.", source_row[4], previous_date),
                            ("VAR. DIARIA", None, date_value),
                        ]
                        current_average = re.sub(
                            r"\d{1,2}/\d{1,2}/\d{2,4}", "", str(source_row[3] or "")
                        ).replace(",", ".").strip()
                        previous_average = re.sub(
                            r"\d{1,2}/\d{1,2}/\d{2,4}", "", str(source_row[4] or "")
                        ).replace(",", ".").strip()
                        try:
                            daily_variation = float(current_average) - float(previous_average)
                        except ValueError:
                            daily_variation = None
                        statistics[-1] = ("VAR. DIARIA", daily_variation, date_value)
                        for statistic, value, row_date in statistics:
                            if value is None and statistic != "VAR. DIARIA":
                                continue
                            if statistic == "VAR. DIARIA" and daily_variation is None:
                                continue
                            value = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", str(value or ""))
                            if value is not None and str(value).strip():
                                value = str(value).replace(",", ".").strip()
                            else:
                                value = None
                            rows.append([
                                heading, "MERCADOS", statistic, market,
                                row_date.strftime(format), value,
                            ])

                for line in page.extract_text_lines():
                    text = re.sub(r"\s+", " ", line["text"]).strip()
                    producer_match = re.search(
                        r"(P/A\s+\w+)\s+(\d+[,.]\d+)\s+(\d+[,.]\d+)\s+"
                        r"(\d+[,.]\d+)\s+(\d+[,.]\d+)",
                        text,
                        re.IGNORECASE,
                    )
                    if producer_match:
                        minimum, maximum, current, previous = producer_match.groups()[1:]
                        producer_date = date_value
                        producer_previous_date = previous_date
                        producer_values = [
                            ("MÍN.", minimum, producer_date),
                            ("MÁX.", maximum, producer_date),
                            ("PROM.", current, producer_date),
                            ("PROM.", previous, producer_previous_date),
                            ("VAR. DIARIA", float(current.replace(",", ".")) - float(previous.replace(",", ".")), producer_date),
                        ]
                        for statistic, value, row_date in producer_values:
                            rows.append([
                                "PRECIO REFERENCIAL DE POLLO VIVO AL PRODUCTOR (Bs./Kg.)",
                                "TIPO DE POLLO", statistic, producer_match.group(1),
                                row_date.strftime(format), value.replace(",", ".") if isinstance(value, str) else value,
                            ])

            dataframe = pd.DataFrame(rows, columns=["nv1", "nv2", "nv3", "nv4", "fecha", "valor"])

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

        Returns:
            bool: False if the data is valid, True on validation failure / error.
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

            return False
        except Exception:
            traceback.print_exc()
            return True
