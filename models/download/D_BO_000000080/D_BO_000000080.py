from models.download.Download_Base import Download_Base
import pandas as pd
from models.download.tools.download_tools import format_date,last_day_month, read_excel, get_date_method_2
from models.download.BCB_Sector_Monetario import BCB_Sector_Monetario

class D_BO_000000080(BCB_Sector_Monetario):

    def get_file_url(self, main_url, updated_to, key_words = "cuentas no bancos",format='%Y-%m-%d'):
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
        # Call the superclass method to get a list of file URLs from the main page        
        files_urls = super().get_file_url_main(main_url=main_url,updated_to=updated_to, key_words=key_words)
        return files_urls
    
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
            df:pd.DataFrame = read_excel(file['tmp_path'])
            df = df.dropna(how='all').dropna(how='all',axis=1).reset_index(drop=True)
            
            date = get_date_method_2(dataframe=df)
            
            year = date[1]
            month = date[0]
            day = last_day_month(year=year,month=month)            
            
            date_formated = format_date(f"{year}-{month}-{day}")
            print(date_formated)
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

Executor_D_BO_000000080 = D_BO_000000080
Robot = D_BO_000000080
