from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date, text_extract, month_abr_to_number, month_to_number
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import re
import traceback
import shutil
import os


class D_BO_000000024(Download_Base):

    def verify_download(self, main_url, updated_to, path, format='%Y-%m-%d'):
        """
        Verifies and downloads files dated after the specified update date, and saves them to a temporary path.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            table_rows_xpath = '//table/tbody/tr'
            re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')
                
                page.wait_for_selector('//table')
                table_rows = page.query_selector_all(table_rows_xpath)
                for row in table_rows:
                    row_text = row.inner_text()
                    date = re.search(re_date,row_text,re.IGNORECASE)
                    if not date:
                        continue
                    date = date.group(1,2,3)
                    month = month_to_number(date[1]) if month_to_number(date[1]) else month_abr_to_number(date[1])

                    formated_date = format_date(f'{date[2]}-{month}-{date[0]}')
                    if formated_date<=updated_to:
                        continue

                    print("Downloading file for date:", formated_date.strftime(format=format))

                    url = urljoin(main_url,row.query_selector('//td/a[@href]').get_attribute('href'))
                    urls.append(url)
                file_paths = self.file_download(urls=urls,path=path)
                if not file_paths:
                    raise ValueError('Download failed')
                    
                # If the list of verified_urls is empty returns NONE
                if not len(file_paths):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return False
                
                return file_paths
            
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []
            finally:
                # Close page and browser
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
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            lines = text_extract(file["tmp_path"])
            matches = [re.search(re_date,line,re.IGNORECASE) for line in lines if re.search(re_date,line,re.IGNORECASE)]
            
            date = matches[-1].group()
            date = format_date(date=date, format='%d/%m/%Y')

            if date>updated_to:
                # Format the update date
                update_to_formatted = date.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                file["download_url"] = '-'
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts

# if __name__ == "__main__":
#     robot = D_BO_000000024()
#     x = robot.verify_download(main_url="https://www.asfi.gob.bo/index.php/carta-informativa.html",
#                               updated_to="2023-11-21", path=r'D:\DATAX\Download_SPIM\base_path\tmp')
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"D:\DATAX\Download_SPIM\base_path\CI_20231231_CartaInformativa.pdf"}],updated_to="2023-01-21")
#     # print(y)
# 

Executor_D_BO_000000024 = D_BO_000000024
Robot = D_BO_000000024
