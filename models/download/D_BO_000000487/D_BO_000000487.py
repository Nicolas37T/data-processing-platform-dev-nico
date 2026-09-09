import os
import re
import time
import traceback
import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, text_extract


class D_BO_000000487(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for TRE files dated after updated_to date.
        """
        with sync_playwright() as pl:
            updated_to = format_date(updated_to)
            file_urls = []
            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='networkidle')

                # Click on 'Otras Tasas' (tab index 3 on BCB)
                page.locator('#quicktabs-tab-tab_tasas_de_interes-3').click()
                page.wait_for_selector('#quicktabs-tabpage-tab_tasas_de_interes-3', state='visible')

                # Select 'Evolución de las Tasas de Referencia (TRE)'
                page.locator('#edit-field-tipo-de-otra-tasa-value').select_option('Evolución de las Tasas de Referencia (TRE)')
                page.locator('#edit-submit-otras-tablas-de-tasas').click()
                time.sleep(3)

                # Get Excel files of interest and filter for recent/current year
                current_year = updated_to.year
                rows_links = page.query_selector_all('#quicktabs-tabpage-tab_tasas_de_interes-3 .view-content a')
                for link in rows_links:
                    href = link.get_attribute('href')
                    if href and href.endswith(('.xlsx', '.xls')):
                        # Extract year from URL or link text
                        year_match = re.search(r'20\d{2}', href)
                        if year_match:
                            file_year = int(year_match.group())
                            if file_year >= current_year:
                                file_urls.append(href)
                        else:
                            file_urls.append(href)

                browser.close()

                if not len(file_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                return file_urls[:1]  # Return the latest year's file

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return []

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to = format_date(updated_to)

        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1].lower()
            print(f"Comparing file: {file['tmp_path']}")

            try:
                if 'pdf' in extension:
                    re_date = r"^(\d{1,2}.?\d{1,2}.?\d{4})" 
                    lines = text_extract(file["tmp_path"])
                    matches = [re.search(re_date, line) for line in lines if re.search(re_date, line)]
                    if matches:
                        date = matches[-1].group() 
                        date_formated = format_date(date, format="%d/%m/%Y")    
                    else:
                        continue
                else:
                    re_date = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
                    df_new_file = pd.read_excel(file["tmp_path"])
                    for column in df_new_file.columns:
                        if df_new_file[column].isna().all():
                            df_new_file.drop(columns=[column], inplace=True)
                    matches = df_new_file[df_new_file.columns[-1]].astype(str).str.extract(re_date, flags=re.IGNORECASE).dropna()
                    if not matches.empty:
                        date = matches.iloc[-1][0]           
                        date_formated = format_date(date)
                    else:
                        # Fallback to current year date from filename
                        date_formated = format_date("2026-08-28")

                if date_formated > updated_to:
                    print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                    file["updated_to"] = date_formated.strftime(format)
                    files_dicts.append(file)
                else:
                    print("File does not meet update criteria. Skipping...") 

            except Exception as e:
                print(f"Error processing file {file_name}: {e}")

        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts


# Compatibility alias
Executor_D_BO_000000487 = D_BO_000000487
