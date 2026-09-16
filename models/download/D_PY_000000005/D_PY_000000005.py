import os
import re
import shutil
import traceback
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number
from models.download.Download_Base import Download_Base

class D_PY_000000005(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        base_url = 'https://www.bcp.gov.py/'
         # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)        

        # Define XPaths for interacting with dropdowns and buttons
        main_container_xpath = '//div[@class="cont_relleno"]'
        download_url_xpath = main_container_xpath + '/p[not(@class)]//a'       
        
        files_urls = []
        try:
            with sync_playwright() as pl:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                # Wait for the year selector to be visible
                page.wait_for_selector(main_container_xpath,state='visible')

                url = base_url + page.locator(download_url_xpath).get_attribute('href')

                if url:
                    files_urls.append(url)
            
            if not len(files_urls):
                print(f"There are NO files after {updated_to.strftime(format)}")
                return []

            print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
            return files_urls
                
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

            df_new_file = pd.read_excel(file['tmp_path'],sheet_name=0)

            df_new_file = df_new_file.dropna(axis=1,how='all')

            date_mask = pd.to_datetime(df_new_file[df_new_file.columns[0]],errors='coerce').notna()
            last_date_index = df_new_file.loc[date_mask].index[-1]
            last_date = df_new_file.loc[last_date_index,df_new_file.columns[0]]
            
            # Check if the file is newer than the provided date
            if last_date>updated_to:
                print(f"File date: {last_date.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = last_date.strftime(format)
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...")

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts

Executor_D_PY_000000005 = D_PY_000000005
Robot = D_PY_000000005
