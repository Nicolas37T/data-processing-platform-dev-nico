import os
import re
import time
import traceback
import pandas as pd
from playwright.sync_api import sync_playwright

from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, text_extract, month_abr_to_number, month_to_number


class D_BO_000000419(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after updated_to date.
        """
        with sync_playwright() as pl:
            updated_to = format_date(updated_to)
            re_date = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\D*(\d{4})"
            files_urls = []

            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='load')

                stop = False
                while not stop:
                    files_rows = page.query_selector_all('div.view-content div.views-row')
                    if not files_rows:
                        break

                    for row in files_rows:
                        title_elem = row.query_selector('div.views-field, div')
                        if not title_elem:
                            continue
                        title = title_elem.inner_text()

                        match = re.search(re_date, title, re.IGNORECASE)
                        if match:
                            day = match.group(1)
                            month = match.group(2)
                            month_num = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                            year = match.group(3)

                            date_formated = format_date(f"{year}-{month_num}-{day}")
                            if date_formated > updated_to:
                                urls = [u.get_attribute('href') for u in row.query_selector_all('a') if u.get_attribute('href')]
                                files_urls.extend(urls)
                            else:
                                stop = True
                                break

                    if stop:
                        break

                    next_btn = page.query_selector('li.pager-next a, .pager-next a')
                    if next_btn:
                        next_btn.click()
                        time.sleep(2)
                        page.wait_for_load_state(state='load')
                    else:
                        break

                browser.close()

                if not len(files_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []

                print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
                return files_urls

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
                date_formated = None

                if 'pdf' in extension:
                    re_date = r"(\d{1,2})\D*((?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{2})\b"
                    lines = text_extract(file["tmp_path"])
                    date_line = [re.search(re_date, line, re.IGNORECASE) for line in lines if re.search(re_date, line, re.IGNORECASE)]
                    if date_line:
                        date = date_line[-1]
                        year = "20" + date.group(3)
                        month = date.group(2)
                        month_num = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                        day = date.group(1)
                        date_formated = format_date(f"{year}-{month_num}-{day}")
                else:
                    re_date = r"(\d{4})\D(\d{1,2})\D(\d{1,2})"
                    df_new_file = pd.read_excel(file["tmp_path"])
                    for column in df_new_file.columns:
                        if df_new_file[column].isna().all():
                            df_new_file.drop(columns=[column], inplace=True)

                    dataframe_to_look = df_new_file.iloc[:10]
                    matches = []
                    for column in dataframe_to_look.columns:
                        values = dataframe_to_look[column].astype(str).str.strip().str.lower()
                        column_matches = values.apply(lambda x: re.search(re_date, x, re.IGNORECASE))
                        matches.extend(column_matches.dropna().tolist())

                    if matches:
                        date = matches[-1]
                        year = date.group(1)
                        month = date.group(2)
                        day = date.group(3)
                        date_formated = format_date(f"{year}-{month}-{day}")

                if not date_formated:
                    print(f"Could not extract date from {file_name}, skipping...")
                    continue

                print(f"Extracted date: {date_formated.strftime(format)}")
                if date_formated > updated_to:
                    print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                    file["updated_to"] = date_formated.strftime(format)
                    files_dicts.append(file)
                else:
                    print("File does not meet update criteria. Skipping...")

            except Exception as e:
                print(f"Error comparing file {file_name}: {e}")

        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts


# Compatibility alias
Executor_D_BO_000000419 = D_BO_000000419
