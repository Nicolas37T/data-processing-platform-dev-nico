import sys, re, traceback
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date,last_day_month, delete_hidden_sheets
from models.download.Download_Base import Download_Base

class D_BO_000000156(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """

        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            link_xpath = '//div[@class="wpb_wrapper"]//a'
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                # Searching for link
                files_link = page.query_selector_all(link_xpath)
                files_link = [link.get_attribute("href") for link in files_link]
                
                if not len(files_link):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link      

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
        quarters = {
            "i": 3,
            "ii": 6,
            "iii": 9,
            "iv": 12,
        }
        help_dict = {}
        # Iterate over each file path
        for file in files_paths: 

            re_year = r'(\d{4})\s*[(]?p?[)]?'
            re_month = r"(\d{1})T.*"
            print(f"Comparing file: {file['tmp_path']}")

            delete_hidden_sheets(file=file["tmp_path"])
            
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"],header=[4])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)            
                   
            columns = df_new_file.columns
            year = int(re.search(re_year,columns[-1]).group(1))
            month = int(re.search(re_month,columns[-1]).group(1))
            month = month * 3
            day = last_day_month(year=year,month=month)            
            
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
    
# if __name__ == "__main__":
#     robot = D_BO_000000156()
#     # x = robot.get_file_url(main_url="https://www.ine.gob.bo/index.php/otros-departamentos-area-urbana-poblacion-por-trimestre-segun-condicion-de-actividad-y-sexo/",updated_to="2023-10-21")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"C:\Users\Kevin Padilla\Downloads\3.05.04.12.xlsx"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000156 = D_BO_000000156
Robot = D_BO_000000156
