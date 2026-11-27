from models.download.Download_Base import Download_Base
import os
import re
import urllib.parse
import calendar
import datetime
import requests
from bs4 import BeautifulSoup
import openpyxl
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from models.download.tools.download_tools import format_date

class D_BO_000000101(Download_Base):

    def get_file_url(self, main_url: str, updated_to: str, key_words: str = "Base Monetaria", format: str = "%Y-%m-%d") -> list:
        """
        Extracts download URLs for files from the main page.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            }
            resp = requests.get(main_url, headers=headers, timeout=25, verify=False)
            if resp.status_code != 200:
                print(f"Error fetching main_url {main_url}: status {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            download_urls = []
            base_domain = "https://www.bcb.gob.bo"

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text().strip()
                clean_href = urllib.parse.unquote(href).lower()
                clean_text = text.lower()
                if ("1. base monetaria.xlsx" in clean_href) or (clean_text == "base monetaria" and clean_href.endswith(".xlsx")):
                    if "multiplicadores" not in clean_href and "determinantes" not in clean_href:
                        full_url = urllib.parse.urljoin(base_domain, href)
                        if full_url not in download_urls:
                            download_urls.append(full_url)
                            print(f"Found download URL: {full_url}")

            return download_urls
        except Exception as e:
            print(f"Error in get_file_url: {e}")
            return []

    def compare_files(self, files_paths: list, updated_to: str, format: str = "%Y-%m-%d"):
        """
        Extract the date from a list of files to compare and filter which are more recent than updated_to.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)

        for file in files_paths:
            tmp_path = file.get("tmp_path")
            if not tmp_path or not os.path.exists(tmp_path):
                continue

            try:
                wb = openpyxl.load_workbook(tmp_path, data_only=True)
                sheet = wb.worksheets[0]
                max_date = None

                for r in range(11, sheet.max_row + 1):
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
                        m = re.search(r"(\d{4})", c1.strip())
                        if m:
                            y = int(m.group(1))
                            if 1900 <= y <= 2100:
                                d_str = f"{y:04d}-12-31"
                                if max_date is None or d_str > max_date:
                                    max_date = d_str

                if max_date:
                    file_date = format_date(max_date)
                    if file_date > updated_to_dt:
                        formatted_date = file_date.strftime(format)
                        print(f"File date: {formatted_date} > {updated_to}. Adding to download list.")
                        file["updated_to"] = formatted_date
                        files_dicts.append(file)
                    else:
                        print(f"File date: {file_date.strftime(format)} <= {updated_to}. Skipping...")
            except Exception as e:
                print(f"Error inspecting file {tmp_path}: {e}")

        if not files_dicts:
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False

        return files_dicts

Executor_D_BO_000000101 = D_BO_000000101
Robot = D_BO_000000101
