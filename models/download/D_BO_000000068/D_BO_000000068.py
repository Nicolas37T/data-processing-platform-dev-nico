from models.download.Download_Base import Download_Base
import re, os, zipfile
from models.download.tools.download_tools import format_date
import pandas as pd
from models.download.CNDC import CNDC

class D_BO_000000068(CNDC):

    def get_file_url(self, main_url, updated_to,key_words="tasas" , format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        return self.get_file_url_main(main_url=main_url, updated_to=updated_to, key_words=key_words, frecuency='anual')

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
            re_year = r"^(\d{4})$"
            print(f"Comparing file: {file['tmp_path']}")

            if "zip" in extension:
                folder_path = os.path.dirname(file['tmp_path'])
                extract_dir = os.path.join(folder_path,os.path.splitext(file_name)[0])
                with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                new_file_name = os.listdir(extract_dir)[0]
                new_file_path = os.path.join(extract_dir,new_file_name)
                file['zip_path'] = file['tmp_path']
                file['tmp_path'] = new_file_path
            
            # delete_hidden_sheets(file=file["tmp_path"])
            
            df_new_file = pd.read_excel(file["tmp_path"],engine='xlrd')
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            # Extract a subset of rows from the DataFrame to search for dates
            dataframe_to_look = df_new_file.iloc[:10]
            matches = []
            for column in dataframe_to_look.columns:
                for index, value in dataframe_to_look[column].items():
                    # Convert the value to lowercase and strip whitespace
                    value_str = str(value).strip().lower()
                    # Search for matches of the date pattern in the value string    
                    match_value = re.search(re_year,value_str)
                    matches.append(match_value)

            # Filter out None matches
            years = [match.group() for match in matches if match]
            year = int(years[-1])            
            
            date_formated = format_date(f"{year}-{12}-{31}")
            # Check if the file is newer than the provided date
            if date_formated>updated_to:
                # Format the update date
                update_to_formatted = date_formated.strftime(format)
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
#     robot = D_BO_000000068()
#     # x = robot.get_file_url(main_url="https://www.cndc.bo/estadisticas/anual.php",updated_to="2023-11-21")
#     # print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\tasa_indisp_2023.zip"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000068 = D_BO_000000068
Robot = D_BO_000000068
