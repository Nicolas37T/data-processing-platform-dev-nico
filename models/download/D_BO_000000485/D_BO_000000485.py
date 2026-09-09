"""Type III download robot for BCB gold price quotations."""

import os
import re
import shutil
from html import unescape
from urllib.parse import urljoin

import pandas as pd
import requests
from unidecode import unidecode

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, month_to_number


class D_BO_000000485(Download_Base):
    """Download historical fine gold quotations from the BCB portal."""

    def check_new_data(
        self,
        main_url,
        updated_to,
        path,
        key_words=None,
        format="%Y-%m-%d",
    ):
        """Build an Excel file with new gold data from the last seven days.

        Args:
            main_url (str): BCB quotations portal URL.
            updated_to (str): Last stored date.
            path (str): Base directory where ``tmp`` will be recreated.
            key_words (str, optional): Base name for the generated file.
            format (str, optional): Input and output date format.

        Returns:
            list[dict]: Generated file metadata, or an empty list when no
            newer records are available or an error occurs.
        """
        tmp_directory = os.path.join(path, "tmp")

        try:
            if os.path.exists(tmp_directory):
                shutil.rmtree(tmp_directory)
            os.makedirs(tmp_directory)

            reference_date = format_date(updated_to, format)
            if not hasattr(reference_date, "strftime"):
                raise ValueError("The reference date is invalid.")

            end_date = pd.Timestamp.now().normalize()
            if pd.Timestamp(reference_date) >= end_date:
                return []
            start_date = end_date - pd.Timedelta(days=6)

            historical_url = urljoin(
                main_url,
                "/librerias/indicadores/metales/anteriores.php",
            )
            parameters = {
                "sdd": start_date.day,
                "smm": start_date.month,
                "saa": start_date.year,
                "edd": end_date.day,
                "emm": end_date.month,
                "eaa": end_date.year,
                "moneda": 92,
                "qlist": 1,
                "mk": 2,
                "range": "METAL",
            }
            response = requests.get(
                historical_url,
                params=parameters,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                timeout=60,
            )
            response.raise_for_status()
            response.encoding = "iso-8859-1"

            records = []
            html_rows = re.findall(
                r'<tr\s+class="listas-fila[12]"[^>]*>(.*?)</tr>',
                response.text,
                re.IGNORECASE | re.DOTALL,
            )

            for html_row in html_rows:
                html_cells = re.findall(
                    r"<td[^>]*>(.*?)</td>",
                    html_row,
                    re.IGNORECASE | re.DOTALL,
                )
                cells = [
                    re.sub(
                        r"\s+",
                        " ",
                        unescape(re.sub(r"<[^>]+>", " ", cell)),
                    ).strip()
                    for cell in html_cells
                ]
                if len(cells) < 4:
                    continue

                date_match = re.search(
                    r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)"
                    r"(?:\s+de)?\s+(\d{4})",
                    cells[1],
                    re.IGNORECASE,
                )
                if not date_match:
                    continue

                day, month_name, year = date_match.groups()
                month = month_to_number(unidecode(month_name))
                if not month:
                    continue

                record_date = pd.Timestamp(
                    year=int(year),
                    month=int(month),
                    day=int(day),
                )
                records.append(
                    {
                        "Nro": len(records) + 1,
                        "Fecha": record_date.strftime(format),
                        (
                            "TIPO DE CAMBIO EN ONZA TROY FINA ORO(S) "
                            "POR UNIDAD DE DOLAR (USD)"
                        ): cells[2],
                        (
                            "TIPO DE CAMBIO EN Bs POR UNIDAD DE "
                            "ONZA TROY FINA ORO"
                        ): cells[3],
                    }
                )

            if not records:
                return []

            dataframe = pd.DataFrame(records)
            dataframe = dataframe.drop_duplicates(
                subset=["Fecha"],
                keep="last",
            ).sort_values("Fecha")
            dataframe["Nro"] = range(1, len(dataframe) + 1)

            latest_date = pd.Timestamp(dataframe["Fecha"].max())
            base_name = unidecode(
                str(key_words or "Metales Preciosos Oro")
            )
            base_name = re.sub(r"[^A-Za-z0-9_-]+", "_", base_name)
            base_name = base_name.strip("_") or "metales_preciosos_oro"
            file_path = os.path.join(
                tmp_directory,
                f"{base_name}_{latest_date.strftime('%Y_%m_%d')}.xlsx",
            )
            dataframe.to_excel(file_path, index=False)

            if (
                not os.path.isfile(file_path)
                or os.path.getsize(file_path) == 0
            ):
                raise ValueError("The generated Excel file is not readable.")

            return [
                {
                    "tmp_path": file_path,
                    "updated_to": latest_date.strftime(format),
                    "download_url": response.url,
                }
            ]

        except Exception as error:
            print(f"Could not download BCB gold quotations: {error}")
            return []


Robot = D_BO_000000485