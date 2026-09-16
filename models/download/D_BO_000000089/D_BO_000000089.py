import traceback
import pandas as pd
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, read_excel
from models.conversion.tools.conversion_tools import search_key_words
from models.download.Download_Base import Download_Base

class D_BO_000000089(Download_Base):

    def get_file_url(self, main_url, updated_to, key_words = "encaje me",format='%Y-%m-%d'):
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
            # XPath to locate elements
            report_xpath = '//button[@data-bcb-url]'
            base_url = "https://www.bcb.gob.bo"
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                page.wait_for_timeout(3*1000)
                iframe = page.frame_locator('iframe[loading="lazy"]')
                links = iframe.locator(report_xpath).all()
                print(f"[LINKS] Found {len(links)} report links on this page")

                # Getting all downloadable elements 
                links = [link for link in links if search_key_words(text=link.inner_text(),key_words=key_words)]                
                # Searching for files matching name_file and constructing URLs
                files_link_searched = [link.get_attribute('data-bcb-url') for link in links ]
                
                if not len(files_link_searched):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link_searched      

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
            df = read_excel(file_name=file["tmp_path"])
            df = df.dropna(how='all').dropna(how='all',axis=1)
            df = pd.to_datetime(df.stack(),errors='coerce')

            date_formated = df.max()
            
            # # Check if the file is newer than the provided date
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

Executor_D_BO_000000089 = D_BO_000000089
Robot = D_BO_000000089
