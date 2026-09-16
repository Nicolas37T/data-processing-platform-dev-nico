"""Conversion robot for the ADA Bolivia input price report."""

import os
import re
from datetime import datetime

import pandas as pd
import pdfplumber
from unidecode import unidecode

from models.conversion.Conversion_Base import Conversion_Base
from models.conversion.tools.conversion_tools import (
    get_pdf_report_page,
    month_to_number,
    search_key_words,
    to_numeric_datax,
)


class D_BO_000000462_02(Conversion_Base):
    def extraction(
        self,
        file_path,
        key_words,
        template_path,
        page_number,
        format="%Y-%m-%d",
    ):
        del template_path

        try:
            extension = os.path.splitext(file_path)[1].lower()
            if extension != ".pdf":
                raise ValueError(f"Unsupported file extension: {extension}")

            report_title = "PRECIOS REFERENCIALES DE INSUMOS"
            target_reports = {
                "MAIZ (BS./QQ.)",
                "SORGO (BS./QQ.)",
                "HARINA INTEGRAL DE SOYA (BS. /TN.)",
                "HARINA SOLVENTE DE SOYA (BS. /TN.)",
            }
            output_columns = [
                "nv1",
                "nv2",
                "nv3",
                "nv4",
                "fecha",
                "valor",
            ]

            with pdfplumber.open(file_path) as pdf:
                page = get_pdf_report_page(
                    pdf,
                    key_words,
                    num_caracteres="ALL",
                    page_number=page_number,
                )
                page_text = page.extract_text() or ""
                if not search_key_words(page_text, report_title):
                    raise ValueError("The input price report was not found.")

                header_words = [
                    word
                    for word in page.extract_words()
                    if word["upright"]
                    and word["top"] < page.height * 0.12
                    and word["x0"] > page.width * 0.80
                ]
                header_words.sort(
                    key=lambda word: (word["top"], word["x0"])
                )
                header_text = " ".join(
                    word["text"] for word in header_words
                )
                date_match = re.search(
                    r"(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})",
                    header_text,
                    re.IGNORECASE,
                )
                if not date_match:
                    raise ValueError("The report date was not found.")

                day, month_name, year = date_match.groups()
                month = month_to_number(unidecode(month_name).lower())
                if not month:
                    raise ValueError(
                        f"Unsupported month name: {month_name}"
                    )
                report_date = datetime(
                    int(year),
                    int(month),
                    int(day),
                ).strftime(format)

                words = page.extract_words()
                anchor_words = [
                    word
                    for word in words
                    if unidecode(word["text"]).strip().upper() == "INSUMOS"
                    and word["x0"] > page.width * 0.68
                ]
                if not anchor_words:
                    raise ValueError(
                        "The input price section anchor was not found."
                    )

                anchor = min(
                    anchor_words,
                    key=lambda word: word["top"],
                )
                section = page.crop(
                    (
                        page.width * 0.68,
                        anchor["bottom"] + 8,
                        page.width,
                        page.height * 0.50,
                    )
                )
                section_text = section.extract_text(
                    x_tolerance=2,
                    y_tolerance=2,
                )
                if not section_text:
                    raise ValueError("The input price section is empty.")

                lines = [
                    re.sub(r"\s+", " ", line).strip()
                    for line in section_text.splitlines()
                    if re.sub(r"\s+", " ", line).strip()
                ]
                records = []
                index = 0

                while index < len(lines):
                    title = lines[index]
                    normalized_title = unidecode(title).upper()
                    if normalized_title not in target_reports:
                        index += 1
                        continue
                    if index + 2 >= len(lines):
                        raise ValueError(
                            f"Incomplete report block: {title}"
                        )

                    header = lines[index + 1]
                    data_line = lines[index + 2]
                    header_parts = header.rsplit(" ", 1)
                    if len(header_parts) != 2:
                        raise ValueError(
                            f"Invalid report header: {header}"
                        )
                    nv2, nv4 = header_parts

                    range_match = re.search(
                        r"(\d+(?:[.,]\d+)?)\s*-\s*"
                        r"(\d+(?:[.,]\d+)?)$",
                        data_line,
                    )
                    if range_match:
                        values = list(range_match.groups())
                        nv3 = data_line[:range_match.start()].strip()
                    else:
                        value_match = re.search(
                            r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|"
                            r"\d+(?:,\d+)?)$",
                            data_line,
                        )
                        if value_match:
                            values = [value_match.group(1)]
                            nv3 = data_line[:value_match.start()].strip()
                        else:
                            values = ["0.0"]
                            nv3 = re.sub(r"[-–—\s/SCsc]+$", "", data_line).strip() or data_line.strip()

                    if not nv3:
                        nv3 = "GENERAL"

                    for value in values:
                        clean_val = str(value or "").strip()
                        if not clean_val or clean_val.lower() in ("-", "--", "s/c", "s/i", "none", "nan", "null"):
                            clean_num = 0.0
                        else:
                            val_norm = clean_val.replace(".", "").replace(",", ".") if "," in clean_val else clean_val
                            try:
                                clean_num = float(re.sub(r"[^\d.-]", "", val_norm))
                            except ValueError:
                                clean_num = 0.0

                        records.append(
                            {
                                "nv1": title,
                                "nv2": nv2,
                                "nv3": nv3,
                                "nv4": nv4,
                                "fecha": report_date,
                                "valor": clean_num,
                            }
                        )

                    index += 3

                if len(records) != 6:
                    raise ValueError(
                        "Expected 6 input price records, "
                        f"found {len(records)}."
                    )

                found_page_number = page.page_number

            metadata = {
                "file_name": os.path.basename(file_path),
                "titles": [report_title],
                "page_number": found_page_number,
            }
            dataframe = pd.DataFrame.from_records(
                records,
                columns=output_columns,
            )
            dataframe["valor"] = dataframe["valor"].fillna(0.0)
            return metadata, dataframe

        except Exception as error:
            print(f"Could not extract the input price report: {error}")
            return ""

    def validate_data_results(
        self,
        dataframe,
        decimal_separator,
        TOLERANCE=6.0,
    ):
        del TOLERANCE

        try:
            if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
                return True
            if "valor" not in dataframe.columns:
                return True

            if dataframe["valor"].isna().any():
                return True

            numeric_values = pd.to_numeric(
                dataframe["valor"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            return bool(numeric_values.isna().any())

        except Exception as error:
            print(f"Could not validate the input price report: {error}")
            return True


Robot = D_BO_000000462_02