import re, traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import text_extract, format_date,last_day_month,  month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000280(Download_Base):

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

            re_date = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})"
            # XPath to locate elements
            element_xpath = '//div[@class="standard-arrow list-divider bullet-top"]//li/a'

            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(600000)
                page = context.new_page()
                page.goto(main_url,wait_until='load')
                
                # Getting all links to extract
                page.wait_for_selector('//*[@id="2023"]', state="visible")
                links_cards = page.query_selector_all('//div[@class="fr-tarjeta"]')
                for link in links_cards:
                    text = link.inner_text()                
                    date = re.search(re_date,text, re.IGNORECASE)
                    if not date:
                        continue
                    year = int(date.group(2))
                    month = date.group(1)
                    month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                    day = last_day_month(year=year, month=month)

                    date_formated = format_date(f"{year}-{month}-{day}")
                    if date_formated>updated_to:
                        url = link.query_selector('//img[contains(@data-src,"pdf.png")]/..').get_attribute('href')
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

        re_date = r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
        
        # Iterate over each file path
        for file in files_paths: 

            
            
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            lines = text_extract(file["tmp_path"])            
           
            dates = [re.search(re_date, line,re.IGNORECASE) for line in lines if re.search(re_date, line,re.IGNORECASE)]
            day, month, year = dates[-1].group(1,2,3)
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            
            date_formated = format_date(f"{year}-{month}-{day}")
            
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

Executor_D_BO_000000280 = D_BO_000000280
Robot = D_BO_000000280
