import re
import os
import zipfile
import traceback
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_to_number, get_date_method_2, last_day_month ,month_abr_to_number
import pandas as pd
from models.download.Download_Base import Download_Base

class D_BO_000000001(Download_Base):

    def get_file_url(self,main_url, updated_to, format='%Y-%m-%d'):
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
            re_date = r'((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})'
            # XPath to locate elements
            date_link_xpath = '//div[@class="table-responsive"]//td//a'

            files_urls = []

            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(5*60*1000)
                page = context.new_page()
                page.goto(main_url)

                # Get all links corresponding to dates                
                date_links = [
                    link for link in page.query_selector_all(date_link_xpath) if re.search(r'bole',link.inner_text(), re.IGNORECASE)]
                print([link.inner_text() for link in date_links])
                # Iterate over date links and filter files after the updated date
                for link in date_links:
                    if not link.get_attribute('href'):
                        continue
                    title = link.inner_text()                    
                    date = re.search(re_date, title,re.IGNORECASE).group(1,2)
                    month = date[0]
                    month = m if(m:=month_to_number(month)) else month_abr_to_number(month)
                    day = last_day_month(year=int(date[1]),month=month)
                    date_formated = format_date(f'{date[1]}-{month}-{day}')
                    if date_formated>updated_to :                        
                        with page.expect_download() as download_info:
                            link.click()
                        download = download_info.value
                        url = download.url
                        files_urls.append(url)

                # Check if any files were found after the updated date
                if not len(files_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []

                print(f"There are {len(files_urls)} files after {updated_to.strftime(format)}")
                return files_urls
            except Exception as e:
                print(f"An error ocurred: {e}")
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
            print(f"Comparing file: {file['tmp_path']}")

            try:
                file_name = os.path.basename(file['tmp_path'])
                extension = os.path.splitext(file_name)[1].lower()

                if 'zip' in extension:
                    excel_extensions = {'.xls', '.xlsx'}
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path, os.path.splitext(file_name)[0])

                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path
                            if os.path.splitext(member_path)[1].lower() in excel_extensions or member.is_dir():
                                zip_ref.extract(member, extract_dir)

                    excel_files = []
                    for root, _, files in os.walk(extract_dir):
                        for f in files:
                            if os.path.splitext(f)[1].lower() in excel_extensions:
                                excel_files.append(os.path.join(root, f))

                    if not excel_files:
                        raise FileNotFoundError(f"No se encontró ningún archivo Excel en el ZIP: {file['tmp_path']}")

                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = excel_files[0]
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"], sheet_name='1')
            
            print("Extracting date from the file...")
            date = get_date_method_2(dataframe=df_new_file,final_index=3)

            if not date:
                print("An error occurred while extracting the date")
                break
            month = date[0]
            year = date[1]
            
            # Check if the file is newer than the provided date
            if ((year == updated_to.year) and (month > updated_to.month)) or (year > updated_to.year) :
                # Get the last day of the month for the update date
                print("File meets update criteria. Adding to filtered files.")
                day = last_day_month(year=year, month=month)
                # Format the update date
                update_to_formatted = f"{year}-{str('%02d' % (month,))}-{day}"
                # Append the date of the file to the dict
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
#     robot = Executor_D_BO_000000001()
#     x = robot.get_file_url(main_url='https://www.asfi.gob.bo/index.php/mv-estadisticas/mv-boletines-estadisticos.html', updated_to='2024-08-31')
#     print(x)

Executor_D_BO_000000001 = D_BO_000000001
Robot = D_BO_000000001
