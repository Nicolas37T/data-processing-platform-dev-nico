import re, traceback
from playwright.sync_api import sync_playwright
from datetime import timedelta
import pandas as pd
from models.download.tools.download_tools import format_date,last_day_month, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000270(Download_Base):

    def get_file_url(self, main_url, updated_to,format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            key_words (str, optional): Keywords to search for he file.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            re_date = r'((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

            base_url = "https://www.economiayfinanzas.gob.bo"

            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                # Navigate to the "deuda interna" page
                deuda_interna_link = base_url + page.query_selector('//a[@data-drupal-link-system-path="viceministerios/vtcp/deuda-interna-tgn"]').get_attribute('href')
                page.goto(deuda_interna_link, wait_until='domcontentloaded')
                print(f"Navigating to {deuda_interna_link}...")

                # Initialize last_file_date to the day after updated_to
                last_file_date = updated_to + timedelta(days=1)

                # while last_file_date>updated_to:
                # Select all rows in the table containing the files
                page.wait_for_selector('//table[@class="table table-striped table-hover table-condensed cols-6"]/tbody//tr',state='visible')
                rows = page.query_selector_all('//table[@class="table table-striped table-hover table-condensed cols-6"]/tbody//tr')
                # print("ROWS",rows)
                for row in rows:
                    # Extract the date from the row text                    
                    date = re.search(re_date,row.inner_text(),re.IGNORECASE).group(1,2)                   
                    year = int(date[1])
                    month = month_to_number(date[0])
                    day = last_day_month(year=year,month=month)
                    date_formated = format_date(f"{year}-{month}-{day}")

                    # Get the URL of the file
                    url = row.query_selector('//a').get_attribute('href')

                    # Check if the file date is after updated_to and if the URL contains "BS"
                    if date_formated>updated_to and "BS" in url.upper():
                        files_urls.append(url)

                    # # Update last_file_date to the date of the last row in the table
                    # last_file_date = re.search(re_date,page.query_selector('//table[@class="table table-striped table-hover table-condensed cols-6"]/tbody//tr[last()]').inner_text(),re.IGNORECASE).group(1,2)
                    # last_file_date = format_date(date=f"{last_file_date[1]}-{month_to_number(last_file_date[0])}-{last_day_month(int(last_file_date[1]),month=month_to_number(last_file_date[0]))}")

                    # # Check if there is a next button and navigate to the next page if it exists
                    # next_button = page.query_selector('//li[@class="next"]/a')
                    # if next_button:
                    #     page.goto(base_url + next_button.get_attribute('href'),wait_until="domcontentloaded")                
                if not len(files_urls):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_urls      

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
        
        # Iterate over each file path
        for file in files_paths:
            
            re_date = r"(\d{1,2}\D\d{1,2}\D\d{4})"
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"], sheet_name=0)
            df_new_file = df_new_file.dropna(axis=1,how='all')

            matches = df_new_file[df_new_file.columns[-1]].astype(str).str.extract(re_date).dropna()
            last_date = matches.iloc[0,0].split('.')

            date_formated = format_date(f"{last_date[2]}-{last_date[1]}-{last_date[0]}")
            
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

Executor_D_BO_000000270 = D_BO_000000270
Robot = D_BO_000000270
