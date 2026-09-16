import traceback
import requests
import re
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.Download_Base import Download_Base

class D_BO_000000475(Download_Base):

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
        
        file_paths = []
        try:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)

            CODE_INDICATOR = "2195"
        
            # Launch browser and navigate to main URL
            print(f"Launching browser and navigating to {main_url} ...")

            # Send GET request main URL
            response = requests.get(main_url, timeout=10, headers=self.headers)
            main_url_data = response.json()

            # Filter data for the specific indicator
            indicator_data = [item for item in main_url_data['body']['updates'] if item["id"]==int(CODE_INDICATOR)]
            if not indicator_data:
                raise Exception("The indicator does not exist")

            # Get the update date of the indicator
            indicator_date = format_date(indicator_data[0]["updated"])

            # Check if the indicator date is after the updated_to date
            if indicator_date <= updated_to:
                print(f"There are NO files after {updated_to.strftime(format)}")
                return []         
            
            # Construct dimensions URL and get dimensions data
            dims_url = f"https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator/{CODE_INDICATOR}/dimensions?lang=es&format=json&in=1"
            dims_response =requests.get(dims_url, timeout=10, headers=self.headers)
            dims_data = dims_response.json()
            
            # Extract relevant dimensions
            dimensions = [item for item in dims_data['body']['dimensions']]
            dimensions = [item["members"] for item in dimensions]
            dimensions = [str(item['id']) for sublist in dimensions for item in sublist]

            # Construct the data URL
            url = f"https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator/{CODE_INDICATOR}/data?members={'%2C'.join(dimensions)}&lang=es&format=excel&in=1&app=dashboard"
            
            file_paths.append(url)

            # If the list of verified_urls is empty returns NONE
            if not len(file_paths):
                print(f"There are NO files after {updated_to.strftime(format)}")
                return []
            return file_paths
        
        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return ""

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
        re_date = r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\s*(\d{1,2})\s*(\d{4})"

        # Iterate over each file path
        for file in files_paths:
            print(f"Comparing file: {file['tmp_path']}")

            # Extract date from the file
            print("Extracting date from the file...")
            #delete_hidden_sheets(file=file["tmp_path"])
            
            df_new_file = pd.read_excel(file["tmp_path"],sheet_name="metadatos")
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            dates = df_new_file["value"].str.extract(re_date,flags=re.IGNORECASE,expand=True).dropna().iloc[0]
            print(dates)
            year = dates[2]
            month = dates[0]
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            day = dates[1]

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
        
if __name__ == "__main__":
    robot = Executor_D_BO_000000475()
    x =robot.get_file_url(main_url="https://api-cepalstat.cepal.org/cepalstat/api/v1/portal/cepalstat/updates?top=5000&app=portal&lang=es",updated_to='2017-05-03')
    print(len(x))
    print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000466/2019-09-03_1.1.2.xlsx"}]
    # y = robot.compare_files(files_paths=files,updated_to="2019-01-21")
    # print(y)


Executor_D_BO_000000475 = D_BO_000000475
Robot = D_BO_000000475
