import traceback
import re
import os
import zipfile
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_to_number, month_abr_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000482(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
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

            # Define XPaths to interact with the page
            date_xpath = '//div[@class="fondotitulo"]//p[@class="subtitulo_azul" and contains(text(), "Embalses")]/following-sibling::span[@class="subtitulo_azul_chico_claro_fecha"]'

            re_date = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})"
            file_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                # Extract the date from the results and format it
                print("Extracting date ...")
                date = re.search(re_date, page.query_selector(date_xpath).inner_text(), re.IGNORECASE).group(1,2,3)

                month = date[1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)

                date_formated = format_date(f"{date[2]}-{month}-{date[0]}")

                # Check if the date is within the updated range
                if date_formated <= updated_to:
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                
                # Interact with the page to find the element
                link = [link for link in page.query_selector_all('//div[@class="detalle_publicado"]//a[@href]') if re.search(r'caudales.*aporte', link.inner_text(), re.IGNORECASE)]

                # Open a new page from the popup
                with page.expect_popup() as popup_info:
                    link[0].click()
                new_page = popup_info.value

                # Construct the base URL and get the link to the file
                new_page.wait_for_selector('//a[@href]')
                
                with new_page.expect_download() as download_info:
                    new_page.query_selector('//a[@href]').click()
                download = download_info.value
                download_url = download.url

                file_urls.append(download_url)

                # If the list of file_urls is empty returns empty array
                if not len(file_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                return file_urls

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
        re_date = r"(\d{4}-\d{1,2}-\d{1,2})"

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            new_file_extension = os.path.splitext(os.path.basename(file['tmp_path']))[1]            
            if new_file_extension == '.xls':
                df_new_file = pd.read_excel(file["tmp_path"],engine='xlrd',sheet_name="Volumenes")
            elif new_file_extension == '.xlsx':
                df_new_file = pd.read_excel(file["tmp_path"],sheet_name="Volumenes")            

            df_new_file = df_new_file.dropna(how='all', axis=1)
            df_new_file = df_new_file.dropna(thresh=2)
            
            date_mask = df_new_file.map(lambda x: coincidence.group() if(coincidence:=re.search(re_date,str(x))) else pd.NA)
            date_mask = date_mask.dropna(how='all').dropna(how='all',axis=1)

            if date_mask.empty:
                raise ValueError('Theres no date')            

            date = date_mask.iloc[-1,-1]
            
            date_formated = format_date(date)
            
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                print(f"File date: {date_formated.strftime(format)}. Adding to filtered files.")
                file["updated_to"] = date_formated.strftime(format)
                files_dicts.append(file)
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts   
        
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000482()
#     # x =robot.get_file_url(main_url="https://www.cndc.bo/home/index.php",updated_to='2024-08-01')
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000482/cauvolener_24.xls"}]
#     y = robot.compare_files(files_paths=files,updated_to="2024-08-01")
#     print(y)


Executor_D_BO_000000482 = D_BO_000000482
Robot = D_BO_000000482
