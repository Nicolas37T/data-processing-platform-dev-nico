import re
import traceback
import pandas as pd
from random import randint
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, last_day_month, text_extract
from models.download.Download_Base import Download_Base

class D_PY_000000007(Download_Base):

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
        files_urls_container_xpath = '//div[@class="cont_relleno"]/p[not(@class)]'     
        # Regular expression to match month and year in Spanish
        re_date = r'((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

        files_urls = []
        try:
            with sync_playwright() as pl:
                # Launch browser and navigate to main URL
                print(f"[INFO] Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                print("[INFO] Waiting for content to load...")
                page.wait_for_selector(files_urls_container_xpath,state='visible')

                containers = page.locator(files_urls_container_xpath).all()

                for container in containers:
                    
                    link = container.locator('//a[@href]').first
                    if not link.is_visible():
                        continue
                    url = base_url + u if not "http" in (u:=link.get_attribute('href')) else u                    

                    text = url.replace('%20','')
                    date = re.search(re_date, text, re.IGNORECASE)
                    if not date:                    
                        continue
                    
                    date = date.groups()
                    month = m if (m:=month_to_number(date[0])) else month_abr_to_number(date[0])
                    day = last_day_month(year=int(date[1]),month=month)
                    formated_date = format_date(f'{date[1]}-{month}-{day}')
                    
                    if formated_date <= updated_to:                        
                        break
                    files_urls.append(url) 
            # Final log based on collected links
            if not len(files_urls):
                print(f"There are NO files after {updated_to.strftime(format)}")
                return []

            print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
            return files_urls
                
        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return files_urls
    
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

        re_date = r'(?i)((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        # Iterate over each file path
        for file in files_paths:

            new_file_text = text_extract(file['tmp_path'])
            date_matches = [m.groups() for text in new_file_text if (m:=re.search(re_date,text))]

            if not date_matches:                               
                raise ValueError(f"No recognizable date found in file: {file['tmp_path']}")

            new_file_date = date_matches[0]            

            # Convert Spanish month to numeric
            month = m if (m:=month_to_number(new_file_date[0])) else month_abr_to_number(new_file_date[0])

            # Construct complete date (end of the month)
            day = last_day_month(year=int(new_file_date[1]),month=month)
            last_date = format_date(f'{new_file_date[1]}-{month}-{day}')
             
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

Executor_D_PY_000000007 = D_PY_000000007
Robot = D_PY_000000007
