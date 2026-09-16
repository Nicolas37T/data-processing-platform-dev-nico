from models.download.Download_Base import Download_Base
import traceback
import pandas as pd
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, read_excel
from models.download.BCB_Boletin_Mensual import BCB_Boletin_Mensual

class D_BO_000000265(BCB_Boletin_Mensual):

    def get_file_url(self, main_url, updated_to, key_words = "remesas trabajadores origen",format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            print(f"[INIT] Parsed 'updated_to' date: {updated_to.strftime(format)}")

            # XPaths            
            report_xpath = '//a[@class="bcb-ext-link bcb-ext-link-file"]'
            exact = False

            base_url = "https://www.bcb.gob.bo"

            try:
                print(f"[BROWSER] Launching Chromium browser")
                browser = pl.chromium.launch(headless=True)

                print("[BROWSER] Creating browser context")
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
                )

                page = context.new_page()
                print(f"[NAVIGATION] Navigating to URL: {main_url}")
                page.goto(main_url, wait_until='domcontentloaded')

                download_urls = []

                links = page.locator(report_xpath).all()
                print(f"[LINKS] Found {len(links)} report links on this page")

                for idx, link in enumerate(links, start=1):
                    link_text = link.inner_html().strip()
                   
                    link_download_url = base_url + link.get_attribute('href')

                    print(f"[LINK {idx}] Evaluating link text: {link_text}")

                    if exact:
                        if self.exact_coincidence(text=link_text, key_word=key_words):
                            download_urls.append(link_download_url)
                            print(f"[MATCH] Exact match found. URL added: {link_download_url}")
                    else:
                        if (
                            self.exact_coincidence(text=link_text, key_word=key_words)
                            or self.search_key_words(link_text, key_word=key_words)
                        ):
                            download_urls.append(link_download_url)
                            print(f"[MATCH] Keyword match found. URL added: {link_download_url}")

                if not download_urls:
                    print(f"[RESULT] No files found after {updated_to.strftime(format)}")
                    return []

                print(f"[RESULT] Total download URLs collected: {len(download_urls)}")
                return download_urls

            except Exception as e:
                print(f"[ERROR] An exception occurred: {e}")
                traceback.print_exc()
                return []

            finally:
                print("[CLEANUP] Closing browser resources")
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()
    
    def compare_files(self, files_paths, updated_to, format='%Y-%m-%d'):
        """
        Extract the date from a list of files to compare and filter which are more recent than the updated_to date.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list or bool: A list of dictionaries with information about files that meet the criteria of being more recent than 'updated_to'. Returns False if no more recent files are found.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []
        
        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        help_dict = {}
        # Iterate over each file path
        for file in files_paths:
            
            df = read_excel(file['tmp_path'],headers=None)
            date_df = sorted(pd.to_datetime( df.stack(),errors='coerce').dropna().to_list())
            date_formated = date_df[-1] + pd.offsets.MonthEnd(0)
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                # Format the update date
                update_to_formatted = date_formated.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                files_dicts.append(file)
                
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False

        return files_dicts

Executor_D_BO_000000265 = D_BO_000000265
Robot = D_BO_000000265
