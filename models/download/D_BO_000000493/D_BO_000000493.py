import os
import re
import shutil
import traceback
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.conversion.tools.conversion_tools import search_key_words
from models.download.Download_Base import Download_Base


class D_BO_000000493(Download_Base):

    def verify_download(self, main_url, updated_to, path, key_words="", format='%Y-%m-%d'):
        """
        Download files after updated_to date by interacting with CNDC web form,
        saving them into a temporary folder.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            key_words (str, optional): Keywords to search for the file on the page.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of dicts with 'tmp_path' and 'download_url'.
                  Returns empty list if no files or on error.
        """
        # Ensure correct URL for the operational results section
        if "resultados-operativos" not in main_url:
            main_url = "https://www.cndc.bo/resultados-operativos/"

        with sync_playwright() as pl:
            updated_to_dt = format_date(updated_to)

            # Recreate clean temporary directory
            path = os.path.join(path, "tmp")
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)

            tab_1_xpath = '//*[@id="se-nav-tabs"]//li/a'
            tab_2_xpath = '//button[@data-prog="precmp"]'

            try:
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                context.set_default_timeout(5 * 60 * 1000)
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                page.wait_for_selector(tab_1_xpath, state="visible")
                tab_1 = [
                    item for item in page.locator(tab_1_xpath).all()
                    if search_key_words(text=item.inner_text(), key_words="programa")
                ]
                if not tab_1:
                    raise ValueError("Level 1 Tab not found")
                tab_1[0].click()
                page.wait_for_timeout(2 * 1000)

                page.wait_for_selector(tab_2_xpath, state="visible")
                page.locator(tab_2_xpath).first.click()
                page.wait_for_timeout(2 * 1000)

                file_paths = []
                today = datetime.today()
                cur_date = updated_to_dt

                while cur_date < today:
                    cur_date = cur_date + timedelta(days=1)
                    date_str = cur_date.strftime("%Y-%m-%d")
                    print(f"Checking DATE: {date_str}")

                    page.locator('#precmp-fecha-select').fill(date_str)
                    page.wait_for_timeout(2 * 1000)
                    page.wait_for_selector("#precmp-container", state='visible')

                    not_found = page.locator("//*[@id='precmp-container']/p[contains(@class,'sin-empty-msg')]")
                    if not_found.count() > 0:
                        print(f"Date {date_str} has no available data, continuing...")
                        continue

                    with page.expect_download() as download_info:
                        page.locator("#precmp-export-btn").click()

                    download = download_info.value
                    download_filename = f"{date_str}_{download.suggested_filename}"
                    download_path = os.path.join(path, download_filename)

                    download.save_as(download_path)
                    file_paths.append({
                        'tmp_path': download_path,
                        'download_url': "-",
                    })
                    page.wait_for_timeout(1 * 1000)

                if not len(file_paths):
                    print(f"There are NO files after {updated_to_dt.strftime(format)}")
                    return []
                return file_paths

            except Exception as e:
                print(f"An error occurred: {e}")
                traceback.print_exc()
                return []
            finally:
                if 'browser' in locals():
                    browser.close()

    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from each downloaded file and filter those newer than updated_to.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: List of file dictionaries with 'updated_to' or False if no newer files.
        """
        print("Comparing files...")
        files_dicts = []
        updated_to_dt = format_date(updated_to)

        for file in files_paths:
            file_name = os.path.basename(file.get("tmp_path", ""))
            match = re.search(r"(\d{4}-\d{2}-\d{2})", file_name)

            if match:
                date_formated = format_date(match.group(1))
            elif "updated_to" in file:
                date_formated = format_date(file["updated_to"])
            else:
                date_formated = None

            if not date_formated:
                print(f"Could not extract date from {file_name}. Skipping...")
                continue

            if date_formated > updated_to_dt:
                print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                item = file.copy()
                item["updated_to"] = date_formated.strftime(format)
                files_dicts.append(item)
            else:
                print(f"File date {date_formated.strftime(format)} does not exceed updated_to. Skipping...")

        if not len(files_dicts):
            print(f"There are NO files after {updated_to_dt.strftime(format)}")
            return False
        return files_dicts


Executor_D_BO_000000493 = D_BO_000000493
Robot = D_BO_000000493
