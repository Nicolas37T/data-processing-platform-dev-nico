import sys, re, traceback
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000251(Download_Base):

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

            re_date = r'(\d{4})\D(\d{1,2})\D(\d{1,2})'

            base_url = "https://senamhi.gob.bo/"
            files_urls = []

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')
                
                # page.wait_for_selector('//div[@class="table-responsive"]//button',state="attached")
                link = page.query_selector('//object').get_attribute("data")
                page.goto(link,wait_until='domcontentloaded')
                page.wait_for_selector('//div[@class="table-responsive"]//a',state="visible")
                dates = [re.search(re_date, element.inner_text()) for element in page.query_selector_all('//table[@class="table table-striped table-hover"]//tr[2]/th') if re.search(re_date, element.inner_text())]

                date = dates[-1].group(1,2,3)
            
                date_formated = format_date(f"{date[0]}-{date[1]}-{date[2]}")
                
                if date_formated <= updated_to or len(page.query_selector_all('//table[@class="table table-striped table-hover"]//tr[4]/td'))<4:
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                
                button = page.query_selector('//div[@class="table-responsive"]//a')
                download_url = base_url + button.get_attribute('href').replace("./","")
                files_urls.append(download_url)
                print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
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

            re_date = r'(\d{4})\D(\d{1,2})\D(\d{1,2})'
            
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            tables = pd.read_html(file["tmp_path"])
            df_new_file = tables[0]
            
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            dates = [re.search(re_date, line[1]) for line in df_new_file.columns if re.search(re_date, line[1])]
            date = dates[-1].group(1,2,3)
            
            date_formated = format_date(f"{date[0]}-{date[1]}-{date[2]}")
            
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
#     robot = D_BO_000000251()
#     x = robot.get_file_url(main_url="http://senamhi.gob.bo/index.php/pcpn",updated_to="2024-5-21")
#     print(len(x))
#     print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"C:\Users\Kevin Padilla\Downloads\archivo.xls"}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000251 = D_BO_000000251
Robot = D_BO_000000251
