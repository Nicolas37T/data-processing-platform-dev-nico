from models.download.Download_Base import Download_Base
import os
import re
import urllib.parse
import calendar
import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup
import openpyxl
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from models.download.tools.download_tools import (
    format_date,
    delete_hidden_sheets,
)


class D_BO_000000103(Download_Base):
    """
    Download robot for D_BO_000000103:
    Origen de la liquidez Total (BCB)
    """

    def get_file_url(
        self,
        main_url: str,
        updated_to: str,
        key_words: str = "origen liquidez total",
        format: str = "%Y-%m-%d",
    ) -> list:
        """
        Extracts download URLs for files matching key_words from main_url.
        """
        print(f"Scraping file URLs from: {main_url}")
        files_urls = []
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
                        "4. origen de la liquidez total.xlsx" in href_lower
                        or ("origen de la liquidez total" in text and href_lower.endswith(".xlsx"))
                        or ("origen de la liquidez total" in href_lower and href_lower.endswith(".xlsx"))
                    )

                    if is_target_file and "desagregado" not in href_lower and "desagregado" not in text:
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
        updated_to_dt = format_date(updated_to)

        for file in files_paths:
            tmp_path = file.get("tmp_path")
            if not tmp_path or not os.path.exists(tmp_path):
                continue

            print(f"Comparing file: {tmp_path}")
            try:
                delete_hidden_sheets(file=tmp_path)
            except Exception:
                pass

            try:
                wb = openpyxl.load_workbook(tmp_path, data_only=True)
                sheet = wb.worksheets[0]
                max_date = None

                for r in range(1, sheet.max_row + 1):
                    c1 = sheet.cell(r, 1).value
                    if c1 is None:
                        continue
                    if isinstance(c1, (datetime.datetime, datetime.date)):
                        y = c1.year
                        m = c1.month
                        _, last_day = calendar.monthrange(y, m)
                        d_str = f"{y:04d}-{m:02d}-{last_day:02d}"
                        if max_date is None or d_str > max_date:
                            max_date = d_str
                    elif isinstance(c1, (int, float)):
                        y = int(c1)
                        if 1900 <= y <= 2100:
                            d_str = f"{y:04d}-12-31"
                            if max_date is None or d_str > max_date:
                                max_date = d_str
                    elif isinstance(c1, str):
                        m_date = re.search(r"(\d{4})-(\d{1,2})", c1.strip())
                        if m_date:
                            y = int(m_date.group(1))
                            m = int(m_date.group(2))
                            _, last_day = calendar.monthrange(y, m)
                            d_str = f"{y:04d}-{m:02d}-{last_day:02d}"
                            if max_date is None or d_str > max_date:
                                max_date = d_str

                if max_date:
                    file_date = format_date(max_date)
                    if file_date > updated_to_dt:
                        update_to_formatted = file_date.strftime(format)
                        print(f"File date: {update_to_formatted}. Adding to filtered files.")
                        file["updated_to"] = update_to_formatted
                        files_dicts.append(file)
                    else:
                        print(f"File date: {file_date.strftime(format)} <= {updated_to_dt.strftime(format)}. Skipping...")
            except Exception as e:
                print(f"Error processing file {tmp_path}: {e}")

        if not len(files_dicts):
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False

        return files_dicts


Executor_D_BO_000000103 = D_BO_000000103
Robot = D_BO_000000103
