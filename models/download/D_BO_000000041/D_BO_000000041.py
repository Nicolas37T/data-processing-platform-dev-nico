import sys, time, re, traceback, os
sys.path.append("..")
from playwright.sync_api import sync_playwright, expect
import pandas as pd
from models.download.tools.download_tools import format_date, text_extract, delete_hidden_sheets, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000041(Download_Base):
    def verify_url(self,url, retries=3, wait_time=3, timeout=120, is_download_url=False):
        return True

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
            # Regular expression to match dates
            re_date = r"(\d{1,2})\s*\w*\s*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s*\w*\s*(\d{4})"
            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='domcontentloaded')

                max_retries = 5
                for attempt in range(1, max_retries+1):
                    try:
                        print(f"Waiting for page load (attempt {attempt}/{max_retries})")
                        page.wait_for_selector('//a[contains(text(), "Activas")]', state="visible",timeout=10*1000)
                        break
                    except Exception:
                        print("Reloading page")
                        if attempt<max_retries:
                            page.reload(wait_until="domcontentloaded")
                        else:
                            raise TimeoutError("Page doesn't work after retries")
                        
                # Find and click on the "Activas" button
                activas_button = page.query_selector('//a[contains(text(), "Activas")]')
                activas_button.click()
                print("Clicked on ACTIVAS button.")

                # Expect and select "Activas del Sistema Financiero" from the dropdown list
                expect(page.get_by_text("Anual",exact=True))
                select_dropdown_list = page.get_by_label("Tipo de Tasa Activa")
                select_dropdown_list.select_option("Información Empresas")
                
                # Click on the "BUSCAR" button
                buscar_button = page.get_by_role('button',name="Buscar")
                print("Clicked on BUSCAR button.")
                buscar_button.click()
                time.sleep(10)
                # print(f"Selected {select_dropdown_list.locator('//option[@selected="selected"]').inner_text()} from dropdown list.")
                
                # Expect to find data in the table
                page.wait_for_selector('//*[@id="quicktabs-tabpage-tab_tasas_de_interes-1"]',state='visible')
                
                # Get all rows of interest from the page
                files_rows = page.query_selector_all('//*[@id="quicktabs-tabpage-tab_tasas_de_interes-1"]//tr')

                # Filtering rows
                for row in files_rows:
                    title = row.inner_text().lower()
                    date = re.findall(re_date,title)
                    if date:
                        date = date[-1]

                        year = date[2]
                        month = date[1]
                        month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                        day = date[0]

                        date_formated = format_date(f"{year}-{month}-{day}")
                        if date_formated>updated_to:
                            urls = row.query_selector_all('//a')
                            urls = [url.get_attribute("href") for url in urls]
                            files_urls.extend(urls)

                if not len(files_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                
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
        re_date = r"(\d{1,2})\s*\w*\s*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s*\w*\s*(\d{4})"

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            if 'pdf' in extension: 
                lines = text_extract(file["tmp_path"])
                
                date_line = [re.search(re_date,line) for line in lines if re.search(re_date,line)]
                
                date = date_line[-1]

            else:
                delete_hidden_sheets(file=file["tmp_path"])
            
                df_new_file = pd.read_excel(file["tmp_path"])
                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                
                sub_set = df_new_file.iloc[:5]
                dates = []
                for row in range(len(sub_set)):
                    date = [re.search(re_date, str(year)) for year in sub_set.iloc[row] if re.search(re_date, str(year))]
                    dates.extend(date)
                date = dates[-1]
            
            if not date:
                    raise NameError("An error occurred while extracting the date")
            
            year = date.group(3)
            month = date.group(2)
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
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
#     robot = D_BO_000000041()
#     # x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=tasas_interes",updated_to="2023-12-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\PUBLICACION 2023 07 09 TASAS EMP. ACT. INF.XLSX"}, {"tmp_path": r"C:\Users\Kevin Padilla\Downloads\Tss_Nominales_EMPRE_130723.pdf"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000041 = D_BO_000000041
Robot = D_BO_000000041
