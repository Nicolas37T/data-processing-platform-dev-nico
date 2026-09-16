import os
import shutil
import traceback
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000055(Download_Base):

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

        with sync_playwright() as pl:
            # Format the provided date string into a datetime object
            updated_to = format_date(updated_to)
            
            # Define XPaths for the required elements on the webpage
            entidad_checkbox_xpath = '//*[@id="ASPxTreeListEntidades_D"]//td/span'
            departamento_checkbox_xpath = '//*[@id="ASPxTreeListDepartamentos_D"]//td/span'
            tipo_checkbox_xpath = '//*[@id="ASPxTreeTipoSucursal_R-100_D"]' 
            search_button_xpath = '//*[@id="btnBuscar_CD"]'
            export_button_xpath = '//*[@id="btnReporte_CD"]'
            
            # Create a temporary directory for downloads, removing if it already exists
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)
            
            dataframes = []
            try:
                
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(10*60*1000)
                page = context.new_page()
                page.goto(main_url)
                
                # Ensure the page has loaded completely
                page.wait_for_url(main_url)
                
                # # Find and navigate to iframe URL
                # iframe = page.query_selector('iframe#blockrandom')
                # new_url = iframe.get_attribute('src')
                # page.goto(new_url)
                
                # Locate checkboxes and buttons on the page
                entidad_checkbox = page.query_selector_all(entidad_checkbox_xpath)
                departamento_checkbox = page.query_selector_all(departamento_checkbox_xpath)
                tipo_checkbox = page.query_selector(tipo_checkbox_xpath)
                
                # Click on the required type checkbox
                print("Selecting type filter TODOS...")
                tipo_checkbox.click()
                for i_ent in range(len(entidad_checkbox)):
                    if i_ent == 0:
                        continue

                    page.wait_for_selector(entidad_checkbox_xpath,state='visible')
                    entidad_checkbox = page.query_selector_all(entidad_checkbox_xpath)
                    entidad_checkbox[i_ent].click()
                    print(f"Entity {i_ent} selected.")

                    for i_dep in range(len(departamento_checkbox)):
                        if i_dep == 0:
                            continue

                        page.wait_for_selector(departamento_checkbox_xpath,state='visible')
                        departamento_checkbox = page.query_selector_all(departamento_checkbox_xpath)
                        departamento_checkbox[i_dep].click()
                        print(f"Department {i_dep} selected.")               

                        # Click the search button
                        search_button = page.query_selector(search_button_xpath)
                        search_button.click()
                       
                        page.wait_for_url(page.url)
                        print("Waiting for page to load after search...")
                        time.sleep(2)
                        page.wait_for_selector('#Image2',state='hidden')
                        
                        # Click the export button if enabled
                        print("Clicking EXPORTAR button...")
                        page.wait_for_selector(export_button_xpath,state='visible')
                        export_button = page.query_selector(export_button_xpath)
                        is_enabled = export_button.query_selector('//input')
                        
                        if is_enabled:                            
                            with page.expect_download() as download_info:
                                export_button.click()
                            download = download_info.value

                            # Read the downloaded file into a DataFrame
                            df = pd.read_excel(download.path())
                            df = df.dropna(how='all')
                            dataframes.append(df)
                            print("File downloaded and processed successfully.")                            
                        # time.sleep(5)
                        # Deselect department and wait before continuing
                        page.wait_for_selector(departamento_checkbox_xpath,state='visible')
                        departamento_checkbox = page.query_selector_all(departamento_checkbox_xpath)
                        departamento_checkbox[i_dep].click()
                        time.sleep(5)
                    
                    # Deselect entity and wait before continuing
                    page.wait_for_selector(entidad_checkbox_xpath,state='visible')
                    entidad_checkbox = page.query_selector_all(entidad_checkbox_xpath)
                    entidad_checkbox[i_ent].click()
                    time.sleep(5)

                # Merge all downloaded DataFrames into a single file
                merged_dataframe = pd.concat(dataframes)
                today = datetime.today()
                download_path = os.path.join(path, f"{today.strftime('%Y-%m-%d_%H%M%S')}_download.xlsx")
                merged_dataframe.to_excel(download_path,index=False)
                print(f"Merged file saved at {download_path}")
                
                return [{"tmp_path": download_path}]

            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []
            finally:                
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
        re_date = r"(\d{1,2}).(\d{1,2}).(\d{4})"

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            #delete_hidden_sheets(file=file["tmp_path"])
            
            df_new_file = pd.read_excel(file["tmp_path"])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            sub_set = df_new_file.iloc[:5]
            
            dates = []
            for row in range(len(sub_set)):
                date = [re.search(re_date, str(year), re.IGNORECASE) for year in sub_set.iloc[row] if re.search(re_date, str(year),re.IGNORECASE)]
                dates.extend(date)
            date = dates[-1]

            if not date:
                    raise NameError("An error occurred while extracting the date")
            
            year = date.group(3)
            month = date.group(2)
            day = date.group(1)

            date_formated = format_date(f"{year}-{month}-{day}")
                
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
#     robot = Executor_D_BO_000000055()
    # x = robot.verify_download(main_url="https://appweb2.asfi.gob.bo/PaginasPublicas2/VistaPAF/UbicacionPAF.aspx",updated_to="2023-12-21",path=r'D:\DATAX\data-processing-platform\models\download\D_BO_000000055')
    # print(x)
    # y = robot.compare_files(files_paths=[{"tmp_path": r"D:\DATAX\data-processing-platform\models\download\D_BO_000000055\tmp\2025-02-13_123610_download.xlsx"}],updated_to="2023-01-21")
    # print(y)

Executor_D_BO_000000055 = D_BO_000000055
Robot = D_BO_000000055
