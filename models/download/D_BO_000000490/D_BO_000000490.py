import traceback
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract
from models.download.Download_Base import Download_Base

class D_BO_000000490(Download_Base):

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

            re_link = r"\d{8}.pdf$"
            file_urls = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36', ignore_https_errors=True)
                page = context.new_page()
                page.goto(main_url,wait_until='load')

                page.wait_for_timeout(3000)                
                
                link_searched = [main_url + link.get_attribute('href') for link in page.query_selector_all('//a[@href]') if re.search(re_link,link.get_attribute('href'), re.IGNORECASE)]

                if link_searched:
                    file_urls.extend(link_searched)                

                # If the list of file_urls is empty returns empty array
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
            print(f"Comparing file: {file['tmp_path']} - {file['download_url']}")            

            # Extract date from the file
            print("Extracting date from the file...")
            lines = text_extract(file["tmp_path"])
            print(lines)
            if not lines:
                matches = [re.search(re_date,line, re.IGNORECASE) for line in lines if re.search(re_date,line, re.IGNORECASE)]
                date = matches[-1].group(1,2,3) 
                
                month = date[1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                date_formated = format_date(f"{date[2]}-{month}-{date[0]}")
            else:
                date_formated = format_date(
                    Path(file["download_url"]).stem,
                    format="%Y%m%d"
                )
            print(f"Date found:{date_formated}")
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
#     robot = Executor_D_BO_000000490()
    # x =robot.get_file_url(main_url="https://mineria.gob.bo/",updated_to='2024-08-01')
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000490/20240805.pdf"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-04")
    # print(y)


Executor_D_BO_000000490 = D_BO_000000490
Robot = D_BO_000000490
