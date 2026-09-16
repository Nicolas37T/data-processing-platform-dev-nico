import traceback
import re
import os
import zipfile
import shutil
import time
from playwright.sync_api import sync_playwright
from datetime import datetime
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number,last_day_month, text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000501(Download_Base):

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
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            # Define XPaths and values to interact with the page
            year_options_xpath = '//*[@id="nav-l1_UHJlY2lvcw"]/following-sibling::div[@class="elfinder-navbar-subtree"]/div[@class="elfinder-navbar-wrapper"]'
            see_list_button_xpath = '//div[@title="ver como lista"]' 
            files_xpath = '//tbody[@class="elfinder-cwd-fixheader"]/tr[@title]'
            download_button_xpath = '//div[@title="Descargar"]'           
            re_date = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\D*(\d{4})"

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')                
                
                # Navigate to the link "Boletin Diario"
                print("Navigating to the target page...")
                link = page.query_selector('//*[@id="menu-item-5082"]/a').get_attribute('href')
                page.goto(link,wait_until='domcontentloaded')

                # Wait for the year selection menu to be visible
                page.wait_for_selector('#nav-l1_UHJlY2lvcw', state="visible")
                time.sleep(5)                

                # Collect year options that match the criteria
                year_options = [(option,option.query_selector('span').inner_text().strip()) for option in page.query_selector_all(year_options_xpath)]
                year_options = [option for option in year_options if int(option[1]) >=updated_to.year]
                print(f"Years matching criteria: {', '.join([opt[1] for opt in year_options])}")
                for year_option in year_options:
                    year_option[0].click()
                    time.sleep(3)

                    # Collect month options within the selected year
                    month_options = [option for option in year_option[0].query_selector_all('//div[@class="elfinder-navbar-subtree"]/div')]
                    print(f"Processing months for year {year_option[1]}...")
                    
                    for month_option in month_options:
                        year = int(year_option[1])
                        month = month_option.query_selector('span').inner_text().strip()                        
                        month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                        day = last_day_month(year=year, month=month)
                        date = format_date(f"{year}-{month}-{day}")

                        if date <=updated_to:
                            continue
                        month_option.click()
                        time.sleep(3)
                        
                        # Click on the relevant button to show daily files
                        searched_button = [button for button in month_option.query_selector_all('//div[@class="elfinder-navbar-wrapper"]') if re.search(r"diario", button.inner_text(), re.IGNORECASE)]
                        
                        if not searched_button:
                            print("This month does not have the button that is being searched")
                            continue
                        searched_button[0].click()
                        time.sleep(5)

                        # Switch to list view if available
                        see_list_button = page.query_selector(see_list_button_xpath)
                        if see_list_button:
                            see_list_button.click()
                        
                        # Wait for the file list to be visible
                        page.wait_for_selector('//tbody[@class="elfinder-cwd-fixheader"]',state="visible")

                        # Process all files in the list
                        files_list = page.query_selector_all(files_xpath)
                        for f in files_list:
                            text = f.get_attribute("title")
                            f_date = re.search(re_date, text, re.IGNORECASE).group(1,2,3)
                            f_month = f_date[1]
                            f_month = month_to_number(f_month) if month_to_number(f_month) else month_abr_to_number(f_month)
                            f_date_formated = format_date(f"{f_date[2]}-{f_month}-{f_date[0]}")

                            if f_date_formated <= updated_to:
                                continue

                            # Click and download the file
                            f.click()
                            time.sleep(2)
                            with page.expect_download() as download_info:
                                page.locator(download_button_xpath).click()
                            download = download_info.value
                            today = datetime.today()
                            download_path = os.path.join(
                                path, f"{today.strftime('%Y-%m-%d_%H%M%S')}_{download.suggested_filename}")
                            download.save_as(download_path)
                            print(f"Downloaded file saved to {download_path}")

                            file_paths.append({
                                    "tmp_path": download_path})   
                    
                if not len(file_paths):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
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
        re_date = r"(\d{1,2})\D*\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\b\D*(\d{4})?"        

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            print(f"Comparing file: {file['tmp_path']}")

            try:
                if "zip" in extension:
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path,os.path.splitext(file_name)[0])
                    
                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            # Normalizar las rutas dentro del archivo ZIP
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path

                            # Extraer el miembro con la ruta normalizada
                            zip_ref.extract(member, extract_dir)
                    while True:
                        new_file_name = os.listdir(extract_dir)[0]
                        extract_dir = os.path.join(extract_dir,new_file_name)
                        
                        if os.path.isfile(extract_dir):
                            break
                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = extract_dir
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # Extract date from the file
            print("Extracting date from the file...")
            
            lines = text_extract(file['tmp_path'])
            
            
            dates = [re.search(re_date, line, re.IGNORECASE) for line in lines if re.search(re_date, line, re.IGNORECASE)]
            date = dates[0].group(1,2,3)
            
            now = datetime.now()
            year = now.year if date[2] is None else date[2]
            month = date[1]
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            date_formated = format_date(f"{year}-{month}-{date[0]}")
            
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
#     robot = Executor_D_BO_000000501()
    # x =robot.verify_download(main_url="http://observatorioagro.gob.bo/",updated_to='2024-07-01',path=r"D:\DATAX\data-processing-platform\models\download\D_BO_000000501")
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"D:\DATAX\data-processing-platform\models\download\D_BO_000000501\tmp\2024-08-19_144250_149. Boletín Diario de Precios Mayorista, 02 de agosto 2024 (1) (1).pdf"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-07-09")
    # print(y)


Executor_D_BO_000000501 = D_BO_000000501
Robot = D_BO_000000501
