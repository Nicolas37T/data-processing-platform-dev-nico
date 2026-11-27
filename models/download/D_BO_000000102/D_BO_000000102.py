import os
import re
import urllib.parse
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import (
    format_date,
    month_abr_to_number,
    month_to_number,
    last_day_month,
    delete_hidden_sheets,
)


class D_BO_000000102(Download_Base):
    """
    Download robot for D_BO_000000102:
    Base Monetaria, Determinantes y Componentes (BCB)
    """

    def get_file_url(
        self,
        main_url: str,
        updated_to: str,
        key_words: str = "determinantes componentes",
        format: str = "%Y-%m-%d",
    ) -> list:
        """
        Extracts download URLs for files matching key_words from main_url.
        """
        print(f"Scraping file URLs from: {main_url}")
        files_urls = []
        kw_list = [k.strip().lower() for k in key_words.split() if k.strip()] if key_words else ["determinantes", "componentes"]

        # 1. Primary extraction via HTTP requests
        try:
            response = requests.get(main_url, headers=self.headers, verify=False, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    text = a_tag.get_text(strip=True).lower()
                    href_lower = href.lower()

                    matches_keywords = all(kw in text or kw in href_lower for kw in kw_list)
                    if matches_keywords and (".xlsx" in href_lower or ".xls" in href_lower):
                        clean_href = href.split("#")[0]
                        full_url = urllib.parse.urljoin(main_url, clean_href)
                        if full_url not in files_urls:
                            files_urls.append(full_url)
        except Exception as e:
            print(f"Requests scraping error: {e}")

        # 2. Fallback via Playwright if no URLs found
        if not files_urls:
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(user_agent=self.headers.get("User-Agent"))
                    page.goto(main_url, timeout=30000, wait_until="domcontentloaded")
                    content = page.content()
                    browser.close()

                    soup = BeautifulSoup(content, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"].strip()
                        text = a_tag.get_text(strip=True).lower()
                        href_lower = href.lower()

                        matches_keywords = all(kw in text or kw in href_lower for kw in kw_list)
                        if matches_keywords and (".xlsx" in href_lower or ".xls" in href_lower):
                            clean_href = href.split("#")[0]
                            full_url = urllib.parse.urljoin(main_url, clean_href)
                            if full_url not in files_urls:
                                files_urls.append(full_url)
            except Exception as e:
                print(f"Playwright fallback error: {e}")

        print(f"Found {len(files_urls)} file URL(s): {files_urls}")
        return files_urls

    def compare_files(
        self,
        files_paths: list,
        updated_to: str,
        format: str = "%Y-%m-%d",
    ) -> list:
        """
        Extract date from files and filter those more recent than updated_to.
        """
        print(f"Comparing files against updated_to = {updated_to}...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)
        re_date = r"^((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))(\d{2})\s*[(]?p?[)]?$"

        for file in files_paths:
            tmp_path = file["tmp_path"]
            print(f"Inspecting file: {tmp_path}")

            try:
                delete_hidden_sheets(file=tmp_path)
            except Exception:
                pass

            try:
                df = pd.read_excel(tmp_path, header=None)
            except Exception as e:
                print(f"Error reading Excel {tmp_path}: {e}")
                continue

            detected_dates = []
            for r in range(min(15, len(df))):
                for c in range(df.shape[1]):
                    val = df.iat[r, c]
                    if pd.isna(val):
                        continue

                    if isinstance(val, (datetime, pd.Timestamp)):
                        year = val.year
                        month = val.month
                        day = last_day_month(year=year, month=month)
                        detected_dates.append(format_date(f"{year}-{month:02d}-{day:02d}"))
                    else:
                        s = str(val).strip().lower()
                        m = re.search(re_date, s)
                        if m:
                            mon_str = m.group(1)
                            yr = int(m.group(2))
                            mon = month_to_number(mon_str) if month_to_number(mon_str) else month_abr_to_number(mon_str)
                            full_yr = 2000 + yr if yr < 100 else yr
                            day = last_day_month(year=full_yr, month=mon)
                            detected_dates.append(format_date(f"{full_yr}-{mon:02d}-{day:02d}"))
                        elif re.search(r"^\d{4}-\d{2}-\d{2}", s):
                            dt = format_date(s[:10])
                            day = last_day_month(year=dt.year, month=dt.month)
                            detected_dates.append(format_date(f"{dt.year}-{dt.month:02d}-{day:02d}"))

            if detected_dates:
                max_date = max(detected_dates)
                if max_date > updated_to_dt:
                    date_str = max_date.strftime(format)
                    print(f"File date ({date_str}) > reference ({updated_to}). Adding to result.")
                    files_dicts.append({
                        "tmp_path": tmp_path,
                        "updated_to": date_str,
                        "download_url": file["download_url"],
                    })
                else:
                    print(f"File date ({max_date.strftime(format)}) <= reference ({updated_to}). Skipping.")
            else:
                print(f"No dates found in {tmp_path}.")

        return files_dicts


Executor_D_BO_000000102 = D_BO_000000102
Robot = D_BO_000000102
