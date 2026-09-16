import traceback
import re
import os
import time
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000487(Download_Base):

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

            # Define XPaths and values to interact with the page
            rows_links_xpath = '//*[@id="quicktabs-tabpage-tab_tasas_de_interes-4"]//div[@class="view-content"]/div[1]//a'
            re_date = r"\d{1,2}.\d{1,2}.\d{4}"
            file_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                # Find and click on the "Otras tasas" button
                page.locator('#quicktabs-tab-tab_tasas_de_interes-4').click()
                print("Clicked on OTRAS TASAS button.")

                # Wait for the relevant table to become visible
                page.wait_for_selector("#quicktabs-tabpage-tab_tasas_de_interes-4", state="visible")

                # Select "Evolución de las Tasas de Referencia (TRE)" from the dropdown list
                page.locator('#edit-field-tipo-de-otra-tasa-value').select_option("Evolución de las Tasas de Referencia (TRE)")
                page.locator('#edit-submit-otras-tablas-de-tasas').click()
                time.sleep(3)

                # Get all URLs of interest from the page
                rows_links =  page.query_selector_all(rows_links_xpath)

                # Loop through rows to extract links and filter by date
                if rows_links:
                    file_urls.extend([link.get_attribute("href") for link in rows_links])

                # If no files were found after the updated_to date
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
        

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            if 'pdf' in extension:
                re_date = r"^(\d{1,2}.?\d{1,2}.?\d{4})" 
                lines = text_extract(file["tmp_path"])
                
                matches = [re.search(re_date,line) for line in lines if re.search(re_date,line)]
                date = matches[-1].group() 
                date_formated = format_date(date, format="%d/%m/%Y")    

            else:
                re_date = r"^(\d{4}.?\d{1,2}.?\d{1,2})"
                df_new_file = pd.read_excel(file["tmp_path"])
                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                print(df_new_file)
                matches = df_new_file[df_new_file.columns[-1]].astype(str).str.extract(re_date,flags=re.IGNORECASE).dropna()
                date = matches.iloc[-1][0]           
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
#     robot = Executor_D_BO_000000487()
    # x =robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=tasas_interes",updated_to='2024-08-01')
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000487/NUEVA TRE GESTION-2024_0.pdf"}, {'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000487/NUEVA TRE GESTION-2024_0.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-05")
    # print(y)


Executor_D_BO_000000487 = D_BO_000000487
Robot = D_BO_000000487
