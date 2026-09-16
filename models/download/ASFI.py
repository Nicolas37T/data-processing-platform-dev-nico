import re 
import os
import time
import traceback 
import zipfile
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
from datetime import datetime
import pandas as pd
from models.download.tools.download_tools import format_date,last_day_month, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class ASFI(Download_Base):

    def get_file_url_main(self, main_url, updated_to,SECTION, KEY_WORDS, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
           
            updated_to = format_date(updated_to)
            today = datetime.today()            
            
            files_urls = []            
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                parsed_url = urlparse(page.url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

                year_options_filtred = [option.get_attribute('value') for option in page.query_selector_all('//select[@name="anio"]/option') if int(option.get_attribute('value'))>=updated_to.year]

                month_options = [option.get_attribute('value') for option in page.query_selector_all('//select[@name="mes"]/option')]

                for year in year_options_filtred:
                    for month in month_options:
                        day = last_day_month(year=int(year),month=int(month))
                        date = format_date(f"{year}-{month}-{day}")
                        if date<=updated_to or date>today:
                            continue

                        year_select = page.query_selector('//select[@name="anio"]')
                        month_select = page.query_selector('//select[@name="mes"]')
                        update_button = page.query_selector('//*[@id="consultaForm"]//button[@class="buttonAsfi"]')

                        year_select.select_option(year)
                        month_select.select_option(month)
                        update_button.click()
                        time.sleep(2)
                        page.wait_for_selector('#resultado')
                        # print([link.get_attribute('href') for link in page.query_selector_all('//*[@id="resultado"]//li/a[@href]')])
                        links = [link for link in page.query_selector_all('//*[@id="resultado"]//li/a[@href]') if re.search(KEY_WORDS,link.get_attribute('href'), re.IGNORECASE)]                       
                        if links:
                            files_urls.extend(links)                

                if not len(files_urls):
                    print("The searched files were not found")

                files_urls = [base_url + link.get_attribute('href').replace('..','') for link in files_urls]   

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
    
    def compare_files_main(self, files_paths, updated_to,RE_DATE,SHEET=None,TYPE=1, format='%Y-%m-%d'):
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
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            print(f"Comparing file: {file['tmp_path']}")
            
            try:
                if "zip" in extension:
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path,os.path.splitext(file_name)[0])
                    
                    excel_extensions = {'.xls', '.xlsx'}
                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            # Normalizar las rutas dentro del archivo ZIP
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path

                            # Extraer solo archivos Excel, ignorar .ods y otros formatos
                            if os.path.splitext(member_path)[1].lower() in excel_extensions or member.is_dir():
                                zip_ref.extract(member, extract_dir)

                    excel_extensions_found = []
                    for root, _, files in os.walk(extract_dir):
                        for f in files:
                            if os.path.splitext(f)[1].lower() in excel_extensions:
                                excel_extensions_found.append(os.path.join(root, f))

                    if not excel_extensions_found:
                        raise FileNotFoundError(f"No se encontró ningún archivo Excel en el ZIP: {file['tmp_path']}")

                    extract_dir = excel_extensions_found[0]
                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = extract_dir
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # delete_hidden_sheets(file=file["tmp_path"])
            
            # Extract date from the file
            new_file_extension = os.path.splitext(os.path.basename(file['tmp_path']))[1]
            new_file_extension = new_file_extension.strip().lower()            
            if new_file_extension == '.xls':
                df_new_file = pd.read_excel(file["tmp_path"],engine='xlrd',sheet_name=None)
            elif new_file_extension == '.xlsx':
                df_new_file = pd.read_excel(file["tmp_path"],sheet_name=None)
            
            matches = []
            for sheet in df_new_file:
                if df_new_file[sheet].empty:
                    continue
                for column in df_new_file[sheet].columns:
                    if df_new_file[sheet][column].isna().all():
                        df_new_file[sheet].drop(columns=[column], inplace=True)
                
                
                # Extract a subset of rows from the DataFrame to search for dates
                dataframe_to_look = df_new_file[sheet].iloc[:10]
                
                for column in dataframe_to_look.columns:
                    for index, value in dataframe_to_look[column].items():
                        # Convert the value to lowercase and strip whitespace
                        value_str = str(value).strip().lower()
                        # Search for matches of the date pattern in the value string    
                        match_value = re.search(RE_DATE,value_str,re.IGNORECASE)
                        if match_value :
                            matches.append(match_value)
            if TYPE == 1:
                date = matches[-1].group(1,2,3)
                month = date[1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            
                date_formated = format_date(f"{date[2]}-{month}-{date[0]}")
            if TYPE == 2:
                date = matches[-1].group()
            
                date_formated = format_date(date)
            if TYPE == 3:
                date = matches[-1].group(1,2)
                month = date[0]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                day = last_day_month(year=int(f"20{date[1]}"),month=month)

                date_formated = format_date(f"{f'20{date[1]}'}-{month}-{day}")
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
    
# if __name__ == "__main__":
#     robot = ASFI()
#     # x = robot.get_file_url(main_url="https://www.asfi.gob.bo/index.php/banco-de-desarrollo-productivo.html",updated_to="2023-5-21")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/media/spim_10009/SBEF/08-BDP/07-Estados Financieros Desagregados/tmp/2024-07-04_170209BDR_EstadosFinancierosDesagregados.zip"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)