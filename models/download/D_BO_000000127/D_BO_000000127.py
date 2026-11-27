from models.download.Download_Base import Download_Base
import os
import re
import urllib.parse
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from models.download.tools.download_tools import (
    format_date,
    month_abr_to_number,
    month_to_number,
    last_day_month,
    delete_hidden_sheets,
)


class D_BO_000000127(Download_Base):
    """
    Download robot for D_BO_000000127:
    Financiamiento Concedido por el Resto del sistema financiero al sector privado por sectores económicos y entidad (BCB)
    """

    def get_file_url(
        self,
        main_url: str,
        updated_to: str,
        key_words: str = "entidad no bancaria",
        format: str = "%Y-%m-%d",
    ) -> list:
        """
        Extracts download URLs for files matching key_words from main_url.
        """
        print(f"Scraping file URLs from: {main_url}")
        files_urls = []
        kw_list = [k.strip().lower() for k in key_words.split() if k.strip()] if key_words else ["entidad", "no", "bancaria"]

        target_url = main_url if "sector-monetario" in main_url else "https://www.bcb.gob.bo/?q=content/sector-monetario"
        base_domain = "https://www.bcb.gob.bo"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }

        try:
            response = requests.get(target_url, headers=headers, verify=False, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    text = a_tag.get_text(strip=True).lower()
                    href_lower = urllib.parse.unquote(href).lower()

                    is_target_file = (
                        "6. financiamiento por destino del crédito, por entidad no bancaria.xlsx" in href_lower
                        or ("no bancaria" in text and href_lower.endswith(".xlsx"))
                        or ("entidad no bancaria" in href_lower and href_lower.endswith(".xlsx"))
                        or (all(kw in text or kw in href_lower for kw in kw_list) and (".xlsx" in href_lower or ".xls" in href_lower))
                    )

                    if is_target_file:
                        clean_href = href.split("#")[0]
                        full_url = urllib.parse.urljoin(base_domain, clean_href)
                        if full_url not in files_urls:
                            files_urls.append(full_url)
                            print(f"Found download URL: {full_url}")
        except Exception as e:
            print(f"Requests scraping error: {e}")

        return files_urls

    def compare_files(self, files_paths: list, updated_to: str, format: str = "%Y-%m-%d"):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to = format_date(updated_to)
        help_dict = {}

        re_date = r"(\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b).*(\b\d{4})\s*[(]?p?[)]?"

        for file in files_paths:
            parsed_url = urllib.parse.urlparse(file['download_url'])
            root_url = os.path.dirname(parsed_url.path)
            file_name = os.path.basename(parsed_url.path)
            extension = os.path.splitext(file_name)[1].replace(".", "").lower()

            print(f"Comparing file: {file['tmp_path']}")

            if 'pdf' in extension:
                help_dict[root_url] = {extension: file}
                continue

            delete_hidden_sheets(file=file["tmp_path"])

            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"], header=[1])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)

            dataframe_to_look = df_new_file.iloc[:10]
            matches = []
            for column in dataframe_to_look.columns:
                for index, value in dataframe_to_look[column].items():
                    value_str = str(value).strip().lower()
                    match_value = re.search(re_date, value_str)
                    if match_value:
                        matches.append(match_value)

            matches = [match for match in matches if match]
            if not matches:
                print("No date match found in the first rows of the file.")
                continue

            months = [match.group(1) for match in matches if match.group(1)]
            years = [match.group(2) for match in matches if match.group(2)]

            year = int(years[-1])
            month = months[-1]
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            day = last_day_month(year=year, month=month)

            date_formated = format_date(f"{year}-{month}-{day}")

            if date_formated > updated_to:
                update_to_formatted = date_formated.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                files_dicts.append(file)
            else:
                print(f"File date: {date_formated.strftime(format)} <= {updated_to.strftime(format)}. Skipping...")

        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False

        files_dicts_with_pdfs = []
        for file in files_dicts:
            parsed_url = urllib.parse.urlparse(file['download_url'])
            root_url = os.path.dirname(parsed_url.path)
            if 'pdf' in help_dict.get(root_url, {}):
                pdf_file = help_dict[root_url]['pdf']
                pdf_file["updated_to"] = file["updated_to"]
                files_dicts_with_pdfs.append(pdf_file)
            files_dicts_with_pdfs.append(file)

        return files_dicts_with_pdfs


Executor_D_BO_000000127 = D_BO_000000127
Robot = D_BO_000000127
