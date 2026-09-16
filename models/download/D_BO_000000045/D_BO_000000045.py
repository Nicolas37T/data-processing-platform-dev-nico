import sys, traceback
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, search_key_words, get_date_method_2,last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000045(Download_Base):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d', key_words="variacion acumulada"):
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
            files_links_xpath = '//div[@class="standard-arrow list-divider bullet-top"]//li'
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)

                files_links = page.query_selector_all(files_links_xpath)
                files_link_searched = [link.query_selector(
                    '//a') for link in files_links if search_key_words(text=link.inner_text().lower(),key_word=key_words) ]
                files_link_searched = [link.get_attribute("href") for link in files_link_searched]

                if not len(files_link_searched):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link_searched
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
            print(f"Comparing file: {file['tmp_path']}")
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"])
            print("Extracting date from the file...")
            date = get_date_method_2(dataframe=df_new_file,final_index=10)

            if not date:
                raise NameError("An error occurred while extracting the date")
            month = date[0]
            year = date[1]
            day = last_day_month(year=year, month=month)
            
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
#     robot = D_BO_000000045()
#     # x = robot.get_file_url(main_url="https://www.ine.gob.bo/index.php/estadisticas-economicas/indice-global-de-actividad-economica-igae/#1584545313102-06cf787f-a790",updated_to="2023-12-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\01.03.xlsx"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000045 = D_BO_000000045
Robot = D_BO_000000045
