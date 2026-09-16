import sys,re
sys.path.append("..")
from playwright.sync_api import sync_playwright
import pandas as pd
from models.download.tools.download_tools import format_date, delete_hidden_sheets, month_abr_to_number, month_to_number, last_day_month, search_key_words
from models.download.Download_Base import Download_Base

class D_BO_000000015(Download_Base):

    def get_file_url(self, main_url, updated_to, key_words="precios promedio", format='%Y-%m-%d'):
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
            element_xpath = '//div[@class="standard-arrow list-divider bullet-top"]//li/a'
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch()
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                page = context.new_page()
                page.goto(main_url)
                
                # Getting all downloadable elements 
                elements = page.query_selector_all(element_xpath)

                # Searching for files matching name_file and constructing URLs
                files_link_searched = [link.get_attribute(
                    'href') for link in elements if search_key_words(text=link.inner_text(),key_word=key_words) ]
                
                if not len(files_link_searched):
                    print("The searched files were not found")

                print("Found files matching the criteria.")
                return files_link_searched
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

            delete_hidden_sheets(file=file["tmp_path"])
            
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"],header=[4,5])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            date = df_new_file.columns[-1]
            if not date:
                raise NameError("An error occurred while extracting the date")
            year = int(date[0])
            month = month_to_number(date[1]) if month_to_number(date[1]) else month_abr_to_number(date[1])
            
            # Check if the file is newer than the provided date
            if ((year == updated_to.year) and (month > updated_to.month)) or (year > updated_to.year) :
                # Get the last day of the month for the update date
                day = last_day_month(year=year, month=month)
                # Format the update date
                update_to_formatted = f"{year}-{str('%02d' % (month,))}-{day}"
                print(f"File date: {update_to_formatted}. Adding to filtered files.")
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
#     robot = D_BO_000000015()
#     # x = robot.get_file_url(main_url="https://www.ine.gob.bo/index.php/ciudades-y-conurbaciones/",updated_to="2023-9-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\Ciu-2024_03_1_Precios_Promedio.xlsx"}],updated_to="2024-01-21")

Executor_D_BO_000000015 = D_BO_000000015
Robot = D_BO_000000015
