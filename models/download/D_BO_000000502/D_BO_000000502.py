import traceback
import os
import zipfile
import shutil
import time
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from models.download.tools.download_tools import format_date, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000502(Download_Base):

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

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')                
                
                # Wait for the year dropdown to become visible
                page.wait_for_selector('#cboYear', state='visible')
                year_options = [option.get_attribute('value') for option in page.query_selector_all('//*[@id="cboYear"]/option')]
                year_options = [option for option in year_options if option != "All" and int(option)>=updated_to.year]
                print(f"Available years for download: {year_options}")

                # Set the necessary checkboxes
                print("Setting necessary checkboxes...")
                page.locator('#chkAllVars').set_checked(checked=True)
                time.sleep(3)
                page.locator('#chkshowNull').set_checked(checked=True)
                page.locator('#chkDocument').set_checked(checked=True)
                page.locator('#chkTermDef').set_checked(checked=True)
                
                # Iterate through available years and download files
                for year in year_options:
                    print(f"Selecting year: {year}")
                    page.locator('#cboYear').select_option(year)
                    time.sleep(2)
                    page.wait_for_selector('#btnDownload', state='visible')

                    with page.expect_download() as download_info:
                        page.locator('#btnDownload').click()
                    download = download_info.value
                    today = datetime.today()
                    download_path = os.path.join(
                        path, f"{today.strftime('%Y-%m-%d_%H%M%S')}_{download.suggested_filename}")
                    download.save_as(download_path)
                    print(f"Downloaded file saved to {download_path}")

                    file_paths.append({
                            "tmp_path": download_path,
                            "download_url":'-'})   
                # Check if no files were downloaded
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
        re_date = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\D*(\d{4})"        

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
                        new_file_name = max(os.listdir(extract_dir), key=lambda x: os.path.getsize(os.path.join(extract_dir, x)))#os.listdir(extract_dir)[0]
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
            
            df_new_file = pd.read_csv(file["tmp_path"])
            
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)            
            
            year = int(df_new_file['YEAR'].iloc[-1])
            month = int(df_new_file['QUARTER'].sort_values().iloc[-1])
            print(year,month)
            month = month * 3
            day = last_day_month(year=year, month=month)
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
#     robot = Executor_D_BO_000000502()
    # x =robot.verify_download(main_url="https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FKM&QO_fu146_anzr=Nv4%20Pn44vr4%20Sv0n0pvny",updated_to='2023-07-01',path=r"D:\DATAX\data-processing-platform\models\download\D_BO_000000502")
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"D:\DATAX\data-processing-platform\models\download\D_BO_000000502\tmp\2024-08-20_093404_DL_SelectFields.zip"}]
    # y = robot.compare_files(files_paths=files,updated_to="2023-07-09")
    # print(y)


Executor_D_BO_000000502 = D_BO_000000502
Robot = D_BO_000000502
