import re
import traceback
import pandas as pd
from random import randint
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, last_day_month
from models.download.Download_Base import Download_Base

class D_PY_000000006(Download_Base):

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
        option_buttons = '//div[@class="cont_relleno"]/p[not(@class)]//a'
        year_options = '//div[@class="cont_relleno"]/h4[not(@class)]/a'
        files_urls_xpath = '//div[@class="cont_relleno"]/p[not(@class)]//a[@href]'     
        # Regular expression to match month and year in Spanish
        re_date = r'((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'

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
                page.wait_for_selector(option_buttons,state='visible')

                # Choose the relevant section/button based on the keyword 'estado'
                choosen_button = [option.get_attribute('href') for option in page.locator(option_buttons).all() if re.search('estado',option.inner_text(),re.IGNORECASE)][0]
                page.goto(choosen_button, wait_until='domcontentloaded')

                # Wait until the year options are loaded
                page.wait_for_selector(year_options,state='visible')

                # Collect URLs for each year page (only from years >= updated_to.year - 1)
                years_urls = [
                    base_url + u if not "http" in (u:=option.get_attribute('href')) else u 
                    for option in page.locator(year_options).all() 
                    if (d:=re.search(r'(\d{4})\/',option.inner_text())) and int(d.group(1))+1>=updated_to.year
                ]
                
                # Loop through year pages to extract individual file links
                for url in years_urls:
                    new_page = context.new_page()
                    new_page.goto(url, wait_until='domcontentloaded')

                    # Get all XLS file links on the page
                    page_links = [
                        u for item in new_page.locator(files_urls_xpath).all() 
                        if '.xls' in (u:=item.get_attribute('href'))
                    ]

                    for link in page_links:
                        text = link.replace('%20','')
                        date = re.search(re_date, text, re.IGNORECASE)
                        if not date:                            
                            continue

                        # Extract and convert date info
                        date = date.groups()
                        month = m if (m:=month_to_number(date[0])) else month_abr_to_number(date[0])
                        day = last_day_month(year=int(date[1]),month=month)
                        formated_date = format_date(f'{date[1]}-{month}-{day}')

                        # If the file is newer than updated_to, add it to the list
                        if formated_date > updated_to:                            
                            url = base_url + link if not "http" in link else link 
                            files_urls.append(url)                    

                    # Wait a short random time to avoid detection/throttling
                    page.wait_for_timeout(randint(2,4)*1000)
                    new_page.close()                
            
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

        re_date = r'(?i)((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        # Iterate over each file path
        for file in files_paths:

            df_new_file = pd.read_excel(file['tmp_path'],sheet_name=0)
            df_new_file = df_new_file.dropna(axis=1, how='all')
            dates = df_new_file[df_new_file.columns[0]].astype(str).str.extractall(re_date).values.tolist()
            last_date = dates[-1]

            month = m if (m:=month_to_number(last_date[0])) else month_abr_to_number(last_date[0])
            day = last_day_month(year=int(last_date[1]),month=month)
            last_date = format_date(f'{last_date[1]}-{month}-{day}')            
            
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

Executor_D_PY_000000006 = D_PY_000000006
Robot = D_PY_000000006
