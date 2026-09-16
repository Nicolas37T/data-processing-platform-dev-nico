import os
import random
import shutil
import traceback
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_CL_000000003(Download_Base):

    def verify_download(self, main_url, updated_to, path,format='%Y-%m-%d'):
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
         # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Erase the previous tmp path and create the a new one
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)

        # Define XPaths for interacting with dropdowns and buttons
        gold_button_xpath = '#hypLnk2_3'
        year_select_xpath = '#DrDwnFechas'
        excel_button_xpath = '#imgButExport' 
        
        file_paths = []
        try:
            with sync_playwright() as pl:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                page.wait_for_selector(gold_button_xpath,state='visible')
                page.locator(gold_button_xpath).click()

                page.wait_for_timeout(2_000)
                page.wait_for_selector(year_select_xpath,state='visible')

                # Get all year options from dropdown and filter by year >= updated_to
                year_options = [item.get_attribute('value') for item in page.locator(year_select_xpath).locator('//option').all()]

                year_options = [item for item in year_options if int(item)>=updated_to.year]

                for year in year_options:
                    print(f"[INFO] Selecting year {year}...")
                    page.locator(year_select_xpath).select_option(year)
                    page.wait_for_timeout(2_000)                   

                    # page.wait_for_selector('#div_gr')                    
                    
                    print(f"[INFO] New data found for year {year}. Downloading...")

                    # Expect the download to be triggered by modal button click
                    with page.expect_download() as dowload_info:
                        page.locator(excel_button_xpath).click()

                    download = dowload_info.value

                    # Generate file name with timestamp
                    today = datetime.today()
                    download_path = os.path.join(
                        path, f"{today.strftime('%Y-%m-%d_%H%M%S')}_{download.suggested_filename}")
                    download.save_as(download_path)
                    print(f"[SUCCESS] File downloaded and saved to: {download_path}")

                    # Append the file info to the list
                    file_paths.append({
                            "tmp_path": download_path,
                            "download_url":'-'
                    })

                    # Random pause between downloads to avoid throttling
                    page.wait_for_timeout(random.randint(2,4)*1000)
                
                # If no files were downloaded, log a message and return an empty list
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

            df_new_file = pd.read_excel(file['tmp_path'])            
            df_new_file = df_new_file.dropna(axis=1,how='all')

            date = pd.to_datetime(df_new_file[df_new_file.columns[0]],errors="coerce")
            date_formatted = date.max()
            print(date_formatted)
            # Check if the file is newer than the provided date
            if date_formatted>updated_to:
                print(f"File date: {date_formatted.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = date_formatted.strftime(format)
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...")

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts

Executor_D_CL_000000003 = D_CL_000000003
Robot = D_CL_000000003
