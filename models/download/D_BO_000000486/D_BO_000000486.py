import traceback
import shutil
from datetime import timedelta
import os
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000486(Download_Base):

    def verify_download(self,main_url, updated_to, path, key_words="", format='%Y-%m-%d'):
        """
        Download the file without comparing dates, and saves them to a temporary path.
        Parameters:
            main_url(str):The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path where the downloaded files will be saved.
            key_words(str,optional): Keywords to search for the file on the page.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download tmp_path for files that meet the criteria.            
            If there is an error or if there are no elements older than the date , it returns an empty list.
        """
        
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            # Erase the previous tmp path and create the a new one        
            path = os.path.join(path, "tmp")

            # Verifed if the folder exist else delete it to create of new
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            # Define XPaths and values to interact with the page
            tab_1_xpath = '//a[@data-tab="result"]'
            tab_2_xpath = '//button[@data-res="dcdr"]'
            
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(60*1000)
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                page.wait_for_selector(tab_1_xpath,state="visible")
                page.locator(tab_1_xpath).first.click()
                page.wait_for_timeout(3*1000)

                page.wait_for_selector(tab_2_xpath,state="visible")
                page.locator(tab_2_xpath).first.click()
                page.wait_for_timeout(3*1000)

                file_paths = []
                while True:
                    updated_to = updated_to + timedelta(days=1)
                    print(f"DATE: {updated_to}")
                    page.locator('#dcdr-fecha-select').fill(updated_to.strftime(format="%Y-%m-%d"))
                    page.wait_for_timeout(3*1000)
                    page.wait_for_selector("#dcdr-container",state='visible')

                    not_found = page.locator("//*[@id='dcdr-container']/p[contains(@class,'sin-empty-msg')]")
                    if not_found.count()>0:
                        break
                    
                    with page.expect_download() as download_info:
                        page.locator("#dcdr-export-btn").click()

                    download = download_info.value                
                    download_path = os.path.join(path,download.suggested_filename)         

                    download.save_as(download_path)
                    file_paths.append(
                        {
                            'tmp_path': download_path,                        
                            'download_url': "-",
                            "updated_to": updated_to.strftime(format=format)
                        }
                    )
                    page.wait_for_timeout(2*1000)

                # If the list of file_urls is empty returns empty array
                if not len(file_paths):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                return file_paths

            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []

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

        # Iterate over each file path
        for file in files_paths:
            date_formated = format_date(file["updated_to"])
            if date_formated>updated_to:
                print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts   
        
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000493()
    # x =robot.get_file_url(main_url="https://www.cndc.bo/estadisticas/index.php",updated_to='2024-08-01')
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"D:\DATAX\data-processing-platform\models\download\D_BO_000000492\deener_130824.zip"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-09")
    # print(y)

Executor_D_BO_000000486 = D_BO_000000486
Robot = D_BO_000000486
