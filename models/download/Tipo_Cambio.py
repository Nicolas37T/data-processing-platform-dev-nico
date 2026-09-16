import sys, re, os, traceback, time, shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pandas as pd
from models.download.tools.download_tools import search_key_words, format_date
from models.download.Download_Base import Download_Base

class Tipo_Cambio(Download_Base):

    def verify_download_main(self, main_url, updated_to, path, key_words = "argentina peso",format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            element_xpath = '//div[@class="standard-arrow list-divider bullet-top"]//li/a'

            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                tipo_cambio_button = page.query_selector('#menu-5')
                tipo_cambio_hist_button = page.query_selector('#menu-19')
                tipo_cambio_button.click()
                tipo_cambio_hist_button.click()

                time.sleep(2)

                select_options = page.query_selector_all('//div[@class="ui-multiselect-menu ui-widget ui-widget-content ui-corner-all"]//ul[@class="ui-multiselect-checkboxes ui-helper-reset"]/li')
                select_options = [option for option in select_options if search_key_words(option.inner_text(),key_word=key_words)]
                print([option.inner_text() for option in select_options])
                
                select_button = page.query_selector('//button/span[@class="ui-icon ui-icon-triangle-2-n-s"]')
                start_date_input = page.query_selector('#fechaInicial')
                end_date_input = page.query_selector('#fechaFinal')
                get_data_button = page.query_selector('#btnSubmit')
                select_button.click()

                select_options[0].query_selector('//input').set_checked(True)
                select_button.click()
                time.sleep(2)
                end_date = datetime.today()
                start_date = end_date - timedelta(weeks=1)
                end_date_input.fill(end_date.strftime('%d-%m-%Y'))
                start_date_input.fill(start_date.strftime('%d-%m-%Y'))

                get_data_button.click()

                page.wait_for_selector('#btnExportExcel',state="visible")
                export_excel_button = page.query_selector('#btnExportExcel')
                with page.expect_download() as download_info:
                    export_excel_button.click()
                download = download_info.value
                download_path = os.path.join(
                    path, f"{download.suggested_filename}.xls")
                download.save_as(download_path)
                file_paths.append({
                    "tmp_path": download_path})

                # If the list of verified_urls is empty returns NONE
                if not len(file_paths):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return False
                
                return file_paths

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

            re_date = r'(\d{4})\D(\d{1,2})\D(\d{1,2})'
            
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            tables = pd.read_html(file["tmp_path"])
            df_new_file = tables[0]
            
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            sub_set = list(df_new_file[df_new_file.columns[2]])
        
            dates = [re.search(re_date, line) for line in sub_set if re.search(re_date, line)]
            date = dates[-1].group(1,2,3)
            
            date_formated = format_date(f"{date[0]}-{date[1]}-{date[2]}")
            
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                # Format the update date
                update_to_formatted = date_formated.strftime(format)
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
                file["updated_to"] = update_to_formatted
                file["download_url"] = '-'
                files_dicts.append(file)
                
            
            else:
                print("File does not meet update criteria. Skipping...") 

        # Check if any files were found after the updated date
        if not len(files_dicts):
            print(f"There are NO files after {updated_to.strftime(format)}")
            return False
        return files_dicts
    
# if __name__ == "__main__":
#     robot = Tipo_Cambio()
#     # x = robot.verify_download(main_url="http://deudaexternapublica.bcb.gob.bo/publico/inicio",updated_to="2023-10-21", path=r'\\10.0.0.9\SPIM\BCB\03-Deuda Externa\03-Tipos de Cambio')
#     # print(len(x))
#     # print(x)
#     files = [{'tmp_path': r"C:\Users\Kevin Padilla\Downloads\DeudaExternaTiposDeCambio-21-05-2024.xls"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)