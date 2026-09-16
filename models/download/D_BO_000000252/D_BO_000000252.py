import sys, re, os, time, traceback,shutil
sys.path.append("..")
from playwright.sync_api import sync_playwright
from datetime import datetime
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base
from lxml import etree
import pandas as pd

class D_BO_000000252(Download_Base):

    def verify_download(self, main_url, updated_to, path, format='%Y-%m-%d'):
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
            # Regular expression to find dates
            re_year = r'^\d{4}$'
            
            # Erase the previous tmp path and create the a new one
            tmp_path = os.path.join(path, 'tmp')
            if os.path.exists(tmp_path):
                shutil.rmtree(tmp_path)
            os.makedirs(tmp_path)

            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='load')

                # Wait until the login selector is visible
                page.wait_for_selector("#ffLogin",state="visible")
                
                # Enter email and password
                email_input = page.query_selector('//*[@id="ffLogin"]//input[@placeholder="Email"]')
                password_input = page.query_selector('//*[@id="ffLogin"]//input[@placeholder="Clave"]')
                submit_button = page.query_selector('//*[@id="ffLogin"]//a[@onclick="submitForm()"]')
                print(password_input.inner_html())
                email_input.fill("karina.centellas@datax.com.bo")
                password_input.fill("3119079")
                submit_button.click()
                print("Submitted login form.")

                # Navigate to the "Series: AgrÃ­cola - Pecuaria" section
                page.wait_for_selector("#accOap",state="visible")
                page.query_selector('//*[@id="accOap"]/div[@class="panel"][2]/div[1]').click()
                page.wait_for_selector("#div_sa_dept",state="visible")
                
                # Select the last 3 years
                [checkbox.set_checked(True) for checkbox in page.query_selector_all('//*[@id="div_sa_dept"]//input[@type="checkbox"]')]

                # Navigate to the "PECUARIA" section
                page.locator('//*[@id="tbSP"]//ul[@class="tabs"]/li').last.click()

                # Check if there are new data after the last downloaded year
                year_options = page.query_selector_all('//*[@id="tbSP"]//input[@name="spAnios_ids[]"]')
                date = re.search(r"(\d{4})", year_options[-1].query_selector('//..').inner_text()).group(1)
                date = format_date(f"{date}-12-31")
                if date<=updated_to:
                    print(f"There are NO data after {updated_to.strftime(format)}")
                    return []
                
                # Select the last 3 years
                [select.set_checked(True) for select in year_options[-3:]]

                # Select all cattles options
                [select.set_checked(True) for select in page.query_selector_all('//*[@id="tbSP"]//input[@name="spGanado[]"]')]

                # Generate and download the report
                page.query_selector("#btnSeries").click()
                time.sleep(2)
                page.wait_for_selector('//div[@class="messager-body panel-body panel-body-noborder window-body"]',state="detached")

                toolbar_frame = page.frame("birtViewer").frame_element().content_frame()
                toolbar_frame.locator('//*[@id="toolbar"]//input[@name="exportReport"]').click()
                time.sleep(2)
                        
                toolbar_frame.locator('#exportFormat').select_option("xls")
                with page.expect_download() as download_info:
                    toolbar_frame.locator('#exportReportDialogokButton').click()
                download = download_info.value
                today = datetime.today()
                download_path = os.path.join(
                    tmp_path, f"{date.strftime('%Y-%m-%d')}_{download.suggested_filename}")
                download.save_as(download_path)
                file_paths.append({
                    "tmp_path":download_path,
                    })
                page.query_selector('//*[@id="tabConainer"]//li[@class="tabs-selected"]/a[@class="tabs-close"]').click()
                time.sleep(2)
                
                # If the list of verified_urls is empty returns NONE
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
        re_date = r'^\b(\d{4})\b$'

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")
            
            tree = etree.parse(file['tmp_path'])
            root = tree.getroot()

            namespaces = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

            rows = root.xpath('.//ss:Table/ss:Row', namespaces=namespaces)
            data = []
            for row in rows:
                cells = row.xpath('ss:Cell/ss:Data', namespaces=namespaces)
                row_data = [cell.text for cell in cells]
                data.append(row_data)

            df_new_file = pd.DataFrame(data)

            dataframe_to_look = df_new_file.iloc[:10]
            matches = []
            for column in dataframe_to_look.columns:
                for index, value in dataframe_to_look[column].items():
                    # Convert the value to lowercase and strip whitespace
                    value_str = str(value).strip().lower()
                    # Search for matches of the date pattern in the value string    
                    match_value = re.search(re_date,value_str,re.IGNORECASE)
                    if match_value :
                        matches.append(match_value)
            print(matches)
            year = matches[-1].group(1)
            date_formated = format_date(f"{year}-12-31")

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
#     robot = D_BO_000000252()
#     # x = robot.get_file_url(main_url="http://bancodedatos.observatorioagro.gob.bo/birt/report/",path=r"\\10.0.0.9\spim\Ministerio de Desarrollo Rural y Tierras\Estadisticas Agropecuarisa VDR\Estadísticas Agropecuarias\03 Pecuarios")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"\\10.0.0.9\spim\Ministerio de Desarrollo Rural y Tierras\Estadisticas Agropecuarisa VDR\Estadísticas Agropecuarias\03 Pecuarios\tmp\2021-12-31_tbl_deptPecuario.xls"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000252 = D_BO_000000252
Robot = D_BO_000000252
