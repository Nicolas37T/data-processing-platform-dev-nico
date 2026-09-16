import re
import os
import traceback
import zipfile
from unidecode import unidecode
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, get_date_method_2, last_day_month
from models.download.Download_Base import Download_Base

class ASFI_Agencias_Bolsa(Download_Base):

    def search_key_words(self,text,key_word):
        text = unidecode(text)

        key_words = key_word.split(' ')
        for k in key_words:
            
            is_in_text = re.search(k,text,re.IGNORECASE)
        
            if not is_in_text:
                return False
        return True    

    def get_file_url_main(self, main_url, key_words):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            name_file (str): The name of the file to search for.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:

            files_link_xpath = "//td/a"            
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)

                # Querying for links
                files_links = page.query_selector_all(files_link_xpath)
                # Filtering links that are not empty
                files_links = [link for link in files_links if link.inner_text() and self.search_key_words(text=link.inner_text(),key_word=key_words)]
                
                if not len(files_links):
                    print("The searched files were not found")

                # Searching for files matching name_file and constructing URLs                
                download_urls =[]
                for link in files_links:
                    with page.expect_download() as download_info:
                        link.click()
                    download = download_info.value
                    download_urls.append(download.url)

                print("Found files matching the criteria.")
                return download_urls
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
        Compares a list of files with a last file, extracts dates from the new files,
        and filters out the files based on the provided date criteria.

        Parameters:
            files_paths (list): List of dictionaries containing information about files.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: List of dictionaries containing information about files that meet the criteria.
        """
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1].lower()

            try:
                if 'zip' in extension:
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path, os.path.splitext(file_name)[0])

                    excel_extensions = {'.xls', '.xlsx'}
                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path
                            if os.path.splitext(member_path)[1].lower() in excel_extensions or member.is_dir():
                                zip_ref.extract(member, extract_dir)

                    excel_extensions_found = []
                    for root, _, files in os.walk(extract_dir):
                        for f in files:
                            if os.path.splitext(f)[1].lower() in excel_extensions:
                                excel_extensions_found.append(os.path.join(root, f))

                    if not excel_extensions_found:
                        raise FileNotFoundError(f"No se encontró ningún archivo Excel en el ZIP: {file['tmp_path']}")

                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = excel_extensions_found[0]
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # Extract date from the file
            extension = os.path.splitext(file['tmp_path'])[1].lower()
            if extension == '.xlsx':
                df_new_file = pd.read_excel(file["tmp_path"], sheet_name=-1)
            elif extension == '.xls':
                df_new_file = pd.read_excel(file["tmp_path"], engine='xlrd', sheet_name=-1)
            
            print("Extracting date from the file...")
            date = get_date_method_2(dataframe=df_new_file,final_index=4)

            if not date:
                raise NameError("An error occurred while extracting the date")
            month = date[0]
            year = date[1]
            day = last_day_month(year=year, month=month)
            formatted_date = format_date(f"{year}-{month}-{day}")
            # Check if the file is newer than the provided date
            if formatted_date>updated_to:
                # Get the last day of the month for the update date
                print(f"File date: {formatted_date}. Adding to filtered files.")
                # Append the date of the file to the dict
                file["updated_to"] = formatted_date.strftime(format=format)
                files_dicts.append(file)

            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts