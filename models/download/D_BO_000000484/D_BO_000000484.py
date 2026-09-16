import traceback
import re
import os
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000484(Download_Base):
    def verify_url(self,url, retries=3, wait_time=3, timeout=120, is_download_url=False):
        return True

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            key_words (str, optional): Keywords to search for he file.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            # Define XPaths and values to interact with the page
            rows_xpath = '//*[@id="quicktabs-tabpage-tab_tasas_de_interes-0"]//tbody/tr'
            re_date = r"(\d{1,2}).(\d{2}).(\d{4})"
            file_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=False)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url,wait_until='domcontentloaded')

                # Wait for the relevant table to become visible
                max_retries = 5
                for attempt in range(1, max_retries+1):
                    try:
                        print(f"Waiting for page load (attempt {attempt}/{max_retries})")
                        page.wait_for_selector("#quicktabs-tabpage-tab_tasas_de_interes-0", state="visible",timeout=10*1000)
                        break
                    except Exception:
                        print("Reloading page")
                        if attempt<max_retries:
                            page.reload(wait_until="domcontentloaded")
                        else:
                            raise TimeoutError("Page doesn't work after retries")

                # Extract rows from the table
                rows =  [row.query_selector_all("td") for row in page.query_selector_all(rows_xpath)]

                # Loop through rows to extract links and filter by date
                for row in rows:
                    links = row[-1].query_selector_all("//a[@href]") + row[-2].query_selector_all("//a[@href]")
                    links = [link.get_attribute("href") for link in links]
                    
                    links_dates = [[link,re_match] for link in links if (re_match:=re.search(re_date,link.replace('%20','_')))]
                    for link in links_dates:
                        date = '_'.join(link[1].group(1,2,3))
                        link[1] = format_date(date,format='%d_%m_%Y')
                        
                    links_filtered = [link[0] for link in links_dates if link[1]>updated_to]

                    if links_filtered:
                        print(f"Adding {len(links_filtered)} new links from this row.")
                        file_urls.extend(links_filtered)

                # If no files were found after the updated_to date
                if not len(file_urls):
                    print(f"There are NO files after {updated_to.strftime(format)}")
                    return []
                return file_urls

            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []

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
        re_date = r"(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})"

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            if 'pdf' in extension: 
                lines = text_extract(file["tmp_path"])
                
                matches = [re.search(re_date,line) for line in lines if re.search(re_date,line)]   

            else:
            
                df_new_file = pd.read_excel(file["tmp_path"])
                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                
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
                
            date = matches[-1].group(1,2,3)
            month = date[1]
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)

            date_formated = format_date(f"{date[2]}-{month}-{date[0]}")            
            
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
#     robot = Executor_D_BO_000000484()
#     x =robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=tasas_interes",updated_to='2024-08-01')
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.pdf"}, {'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000484/TD_08_08_2024.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-05")
    # print(y)


Executor_D_BO_000000484 = D_BO_000000484
Robot = D_BO_000000484
