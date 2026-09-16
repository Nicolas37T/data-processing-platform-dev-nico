"""Download robot for D_BO_000000270 (Deuda Interna TGN - Ministerio de Economia y Finanzas Publicas)."""

import re
import traceback
from urllib.parse import urljoin
import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import (
    format_date,
    last_day_month,
    month_to_number,
)


class D_BO_000000270(Download_Base):
    """Type I download robot for D_BO_000000270."""

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after updated_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list[str]: A list of download URLs for files that meet the criteria.
        """
        updated_to_dt = format_date(updated_to)
        re_date = r'((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        base_url = "https://www.economiayfinanzas.gob.bo"
        files_urls = []

        try:
            with sync_playwright() as pl:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        user_agent=(
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/120.0.0.0 Safari/537.36'
                        )
                    )
                    page = context.new_page()
                    page.goto(main_url, wait_until='domcontentloaded')

                    # Navegar a la página de "Deuda Interna TGN"
                    link_element = page.locator(
                        'a[data-drupal-link-system-path="viceministerios/vtcp/deuda-interna-tgn"]'
                    ).first
                    href = link_element.get_attribute('href')
                    if not href:
                        print("Could not find deuda interna link")
                        return []

                    deuda_interna_link = urljoin(base_url, href)
                    print(f"Navigating to {deuda_interna_link} ...")
                    page.goto(deuda_interna_link, wait_until='domcontentloaded')

                    # Esperar filas de la tabla de archivos
                    page.wait_for_selector(
                        '//table[contains(@class, "table")]/tbody//tr',
                        state='visible',
                        timeout=20000,
                    )
                    rows = page.query_selector_all('//table[contains(@class, "table")]/tbody//tr')

                    for row in rows:
                        row_text = row.inner_text()
                        date_match = re.search(re_date, row_text, re.IGNORECASE)
                        if not date_match:
                            continue

                        month_str, year_str = date_match.group(1, 2)
                        year = int(year_str)
                        month = month_to_number(month_str)
                        day = last_day_month(year=year, month=month)
                        date_formated = format_date(f"{year}-{month:02d}-{day:02d}")

                        link_tag = row.query_selector('a')
                        if not link_tag:
                            continue

                        file_href = link_tag.get_attribute('href')
                        if not file_href:
                            continue

                        full_url = urljoin(base_url, file_href)

                        if date_formated > updated_to_dt and "BS" in full_url.upper():
                            files_urls.append(full_url)

                    if not files_urls:
                        print("The searched files were not found")
                    else:
                        print(f"Found {len(files_urls)} file(s) matching criteria: {files_urls}")

                    return files_urls
                finally:
                    browser.close()

        except Exception as e:
            print(f"An error occurred in get_file_url: {e}")
            traceback.print_exc()
            return []

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract date from files and filter those more recent than updated_to.

        Parameters:
            files_paths (list): List of dicts containing file info ('tmp_path', 'download_url').
            updated_to (str): Latest date already registered.
            format (str, optional): Date format for updated_to. Defaults to '%Y-%m-%d'.

        Returns:
            list[dict] or False: Filtered list of files with 'updated_to', or False if no new files.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)
        re_date = re.compile(r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})")

        for file in files_paths or []:
            try:
                print(f"Comparing file: {file['tmp_path']}")
                df_new_file = pd.read_excel(file["tmp_path"], sheet_name=0)
                df_new_file = df_new_file.dropna(axis=1, how='all')

                matches = df_new_file[df_new_file.columns[-1]].astype(str).str.extract(re_date).dropna()
                if matches.empty:
                    print("No date found in last column, checking other columns...")
                    for col in reversed(df_new_file.columns):
                        matches = df_new_file[col].astype(str).str.extract(re_date).dropna()
                        if not matches.empty:
                            break

                if matches.empty:
                    print(f"Could not extract date from {file['tmp_path']}")
                    continue

                day_val, month_val, year_val = matches.iloc[0]
                day = int(day_val)
                month = int(month_val)
                year = int(year_val)
                date_formated = format_date(f"{year}-{month:02d}-{day:02d}")

                if date_formated > updated_to_dt:
                    update_to_formatted = date_formated.strftime(format)
                    print(f"File date: {update_to_formatted}. Adding to filtered files.")
                    file["updated_to"] = update_to_formatted
                    files_dicts.append(file)
                else:
                    print(f"File date {date_formated.strftime(format)} does not meet update criteria (> {updated_to_dt.strftime(format)}). Skipping...")

            except Exception as err:
                print(f"Error comparing file {file.get('tmp_path')}: {err}")
                traceback.print_exc()

        if not files_dicts:
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False

        return files_dicts
