import sys, time, re, traceback, os
sys.path.append("..")
from playwright.sync_api import sync_playwright, expect
import pandas as pd
from models.download.tools.download_tools import format_date, text_extract, delete_hidden_sheets
from models.download.Download_Base import Download_Base

class D_BO_000000035(Download_Base):

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
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')
                page.wait_for_selector('//a[contains(text(), "Activas")]',state='visible')

                # Find and click on the "Activas" button
                activas_button = page.query_selector('//a[contains(text(), "Activas")]')
                activas_button.click()
                print("Clicked on ACTIVAS button.")

                # Expect and select "Activas del Sistema Financiero" from the dropdown list
                expect(page.get_by_text("Anual",exact=True))
                select_dropdown_list = page.get_by_label("Tipo de Tasa Activa")
                select_dropdown_list.select_option("Destino de Crédito")
                
                # Click on the "BUSCAR" button
                buscar_button = page.get_by_role('button',name="Buscar")
                print("Clicked on BUSCAR button.")
                buscar_button.click()
                time.sleep(2)
                #print(f"Selected {select_dropdown_list.locator('//option[@selected="selected"]').inner_text()} from dropdown list.")
                
                # Expect to find data in the table
                expect(page.locator('//td[@class="bcb_der"]'))
                
                # Get all URLs of interest from the page
                files_urls = page.query_selector_all('//*[@id="quicktabs-tabpage-tab_tasas_de_interes-1"]//td')
                annual_columns = [link.query_selector_all('//a') for link in files_urls[1:3]]
                
                # Filter annual files URLs based on the searched index

                annual_files_urls = [link for list in annual_columns for link in list]
                annual_files_urls = [link.get_attribute("href") for link in annual_files_urls]
                
                # If no files match the criteria, print a message and return an empty list
                if not len(annual_files_urls):
                    print("The searched files were not found")
                    return []
                
                print("Found files matching the criteria.")
                return annual_files_urls
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
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            re_date = r"^(\b\d{4}\b)$"
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            if 'pdf' in extension: 
                lines = text_extract(file["tmp_path"])
                
                date_line = [re.search(re_date,line) for line in lines if re.search(re_date,line)]
                
                date = date_line[-1].group()

            else:
                delete_hidden_sheets(file=file["tmp_path"])
            
                df_new_file = pd.read_excel(file["tmp_path"])
                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                
                sub_set = df_new_file[df_new_file.columns[0]]
                date = [re.search(re_date, str(year)) for year in sub_set if re.search(re_date, str(year))]
                date = date[-1].group()
            
            if not date:
                    raise NameError("An error occurred while extracting the date")
            print(date)
            year = int(date)
                
            # Check if the file is newer than the provided date
            if year>=updated_to.year:
                # Format the update date
                update_to_formatted = f"{year}-12-31"
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
#     robot = D_BO_000000035()
#     x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=tasas_interes",updated_to="2023-9-21")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\30 AC S 2024.xlsx"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000035 = D_BO_000000035
Robot = D_BO_000000035
