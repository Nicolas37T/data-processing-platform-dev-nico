from models.download.Download_Base import Download_Base
import traceback, re, os, zipfile
from models.download.tools.download_tools import format_date, last_day_month, month_abr_to_number, month_to_number, read_excel
import pandas as pd
from models.download.CNDC import CNDC

class D_BO_000000072(CNDC):

    def get_file_url(self, main_url, updated_to,key_words="coincidental" , format='%Y-%m-%d'):
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
            re_date = r"(\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b)|(\b\d{4}$)"
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
            
            df_new_file = read_excel(file["tmp_path"])
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
                    match_value = re.search(re_date,value_str)
                    if match_value and pd.notna(dataframe_to_look[column].iloc[index+2]):
                        matches.append(match_value)
            # Filter out None matches
            matches = [match for match in matches if match]
            
            months = [match.group(1) for match in matches if match.group(1)]
            years = [match.group(2) for match in matches if match.group(2)]
            
            year = int(years[-1])
            month = months[-1]
            month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            day = last_day_month(year=year,month=month)            
            
            date_formated = format_date(f"{year}-{month}-{day}")
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
#     robot = Executor_D_BO_000000072()
#     x = robot.get_file_url(main_url="https://www.cndc.bo/estadisticas/anual.php",updated_to="2025-03-31")
#     print(x)
#     y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\inretkw_2024.zip"}],updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000072 = D_BO_000000072
Robot = D_BO_000000072
