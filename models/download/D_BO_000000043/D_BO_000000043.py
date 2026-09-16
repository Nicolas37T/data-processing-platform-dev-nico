import sys, traceback, re, time, os, shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from models.download.tools.download_tools import format_date, delete_hidden_sheets
from models.download.Download_Base import Download_Base

class D_BO_000000043(Download_Base):

    def verify_download(self, main_url, updated_to,path, format='%Y-%m-%d'):
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
            today = datetime.today()

            excel_button_xpath = '//*[@id="table_1_wrapper"]//button[@class="dt-button buttons-excel buttons-html5 DTTT_button DTTT_button_xls"]'
            dropdown_list_xpath = '//select[@name="table_1_length"]'

            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(600000)
                page = context.new_page()
                page.goto(main_url, wait_until='load')

                # Select the first day of the current year
                from_input_date = page.locator("#table_1_range_from_1")
                input_date: datetime = first_day_year if (first_day_year := format_date(f"{today.year}-01-01")) < updated_to else updated_to
                input_date = input_date.strftime("%d/%m/%Y")
                from_input_date.fill(input_date)
                page.locator('#table_1_wrapper').click()
                time.sleep(5)

                # Select 'All' option from the dropdown list
                dropdown_list = page.locator(dropdown_list_xpath)
                dropdown_list.select_option("All")
                print("Dropdown list option 'All' selected.")
                
                # Wait for some time for the page to load completely
                time.sleep(10)

                last_date = page.query_selector('//*[@id="table_1"]//tr[1]/td[1]')
                last_date = format_date(last_date.inner_text(),"%d/%m/%Y")
                print(last_date)
                if last_date<=updated_to:
                    print(f"There are NO data after {updated_to.strftime(format)}")
                    return []

                # Locate the Excel download button and print its inner text
                excel_button = page.query_selector(excel_button_xpath)
                
                # Expect a download to start when the Excel button is clicked
                with page.expect_download() as download_info:
                    excel_button.click()
                    download = download_info.value
                    download_path = os.path.join(
                        path, download.suggested_filename)
                    download.save_as(download_path)
                    file_paths.append({
                                "tmp_path": download_path})
                    
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
        re_date = r'(\d{1,2}\D\d{1,2}\D\d{4})'

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            delete_hidden_sheets(file=file["tmp_path"])
            
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            sub_set = df_new_file[df_new_file.columns[0]]
            
            dates = [re.search(re_date, str(line)) for line in sub_set if re.search(re_date, str(line))]
            date = dates[0].group()
            date = format_date(date=date, format='%d/%m/%Y')

            if date>updated_to:
                # Format the update date
                update_to_formatted = date.strftime(format)
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
#     robot = D_BO_000000043()
#     # x = robot.verify_download(main_url="https://www.icco.org/statistics/",updated_to="2023-12-21",path=r'D:\DATAX\Download_SPIM\base_path\tmp')
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"D:\DATAX\Download_SPIM\base_path\tmp\tmp\Daily Prices_NEW.xlsx"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000043 = D_BO_000000043
Robot = D_BO_000000043
