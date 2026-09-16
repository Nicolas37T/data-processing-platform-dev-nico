from models.download.Download_Base import Download_Base
import re
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number,month_to_number,last_day_month, read_excel
from models.download.BCB_Boletin_Mensual import BCB_Boletin_Mensual

class D_BO_000000100(BCB_Boletin_Mensual):

    def get_file_url(self, main_url, updated_to, key_words = "financiamiento corto plazo bcb",format='%Y-%m-%d'):
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

            re_year = r'(\d{4})\s*[(]?p?[)]?'
            re_month = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))"
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            df_new_file = read_excel(file["tmp_path"],headers=None)
            df_new_file = df_new_file.dropna(axis=1,how='all').dropna(how='all')
            
            sub_set = df_new_file[df_new_file.columns[0]]
            print(sub_set)
            years = [re.search(re_year, str(line)) for line in sub_set if re.search(re_year, str(line))]
            months = [re.search(re_month, str(value),re.IGNORECASE) for index,value in enumerate(sub_set) if re.search(re_month, str(value),re.IGNORECASE)]
            print(months)
            year = int(years[-1].group())
            month = months[-1].group()
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

Executor_D_BO_000000100 = D_BO_000000100
Robot = D_BO_000000100
