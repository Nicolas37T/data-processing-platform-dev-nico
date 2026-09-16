import sys, time, re, traceback, os
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, text_extract, delete_hidden_sheets, month_abr_to_number, month_to_number, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000420(Download_Base):

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
            re_date = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))\D*(\d{4})"
            files_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url, wait_until='load')

                stop = False
                while stop == False:
                    # Select all rows in the table containing file links
                    files_rows = page.query_selector_all('div.view-content div.views-row')
                    for row in files_rows:
                        # Extract the title from the first cell of the row
                        title = row.query_selector('//div[1]').inner_text()

                        # Search for date in the title using regular expression
                        date = re.search(re_date, title, re.IGNORECASE).group(1,2)
                        
                        if date:

                            year = int(date[1])
                            month = date[0]
                            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                            day = last_day_month(year=year,month=month)

                            # Format the date to compare with updated_to
                            date_formated = format_date(f"{year}-{month}-{day}")
                            if date_formated>updated_to:
                                # Extract URLs from the row
                                urls = [url.get_attribute('href') for url in row.query_selector_all('//a') if ".ods" not in url.get_attribute('href')]                                
                                    
                                files_urls.extend(urls)
                            else:
                                stop = True
                                break
                    # Click the next page button to load more links
                    page.query_selector('//li [@class="pager-next"]').click()
                    time.sleep(2)
                    page.wait_for_load_state(state='load')

                # If no files are found after updated_to
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
        

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            re_year = r"\b(\d{4})\b"
            re_month = r"\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s?$"
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            if 'pdf' in extension: 
                lines = text_extract(file["tmp_path"])
                
                years = [re.search(re_year,line, re.IGNORECASE) for line in lines if re.search(re_year,line, re.IGNORECASE)]
                months = [re.search(re_month,line, re.IGNORECASE) for line in lines if re.search(re_month,line, re.IGNORECASE)]
                
                year = int(years[-1].group(1))
                month = months[-1].group(1)
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                
                day =last_day_month(year=year,month=month)

                date_formated = format_date(f"{year}-{month}-{day}")

            else:

                df_new_file = pd.read_excel(file["tmp_path"],header=[9,11])
                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                
                columns = df_new_file.columns.to_list()
                
                matches = [column for column in columns if re.search(re_month,str(column[1]),re.IGNORECASE) ]
                date = matches[-1]
                
                year = date[0]
                month = date[1].strip()
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)               
                day =last_day_month(year=year,month=month)

                date_formated = format_date(f"{year}-{month}-{day}")
            
            if not date_formated:
                raise NameError("An error occurred while extracting the date")
            
            print(date_formated)    
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
#     robot = D_BO_000000420()
#     # x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=reporte-estadistico",updated_to="2023-7-20")
#     # print(x)
#     y = robot.compare_files(files_paths=[{'download_url': 'https://www.bcb.gob.bo/webdocs/sistema_pagos/SRI_NUEVO%20REPORTE%20ESTADISTICO%20MARZO%202024.pdf', 'tmp_path': '\\\\10.0.0.9\\spim\\BCB\\05-Servicios\\Sistema de Pagos\\Estadísticas\\tmp\\2024-06-06_173119SRI_NUEVO%20REPORTE%20ESTADISTICO%20MARZO%202024.pdf'}, {'download_url': 'https://www.bcb.gob.bo/webdocs/sistema_pagos/SRI_NUEVO%20REPORTE%20ESTADISTICO%20MARZO%2024.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\BCB\\05-Servicios\\Sistema de Pagos\\Estadísticas\\tmp\\2024-06-06_173122SRI_NUEVO%20REPORTE%20ESTADISTICO%20MARZO%2024.xlsx'}],updated_to="2023-01-21")
#     print(y)
#     

Executor_D_BO_000000420 = D_BO_000000420
Robot = D_BO_000000420
