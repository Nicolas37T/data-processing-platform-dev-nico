from models.download.Download_Base import Download_Base
import re
import pandas as pd
from models.download.tools.download_tools import format_date, last_day_month, month_abr_to_number, month_to_number, read_excel
from models.download.BCB_Sector_Externo import BCB_Sector_Externo

class D_BO_000000463(BCB_Sector_Externo):

    def get_file_url(self, main_url, updated_to, format='%Y-%m-%d', key_words="reserva internacional neta banco"):
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
        re_year = r'^\b(\d{4})'
        re_month = r'\b((?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\b'
        print("Comparing files...")
        # List to store file dictionaries
        files_dicts = []

        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        
        # Iterate over each file path
        for file in files_paths: 

            
            print(f"Comparing file: {file['tmp_path']}")
            
            # Extract date from the file
            df = read_excel(file_name=file['tmp_path'])
            df = df.dropna(axis=1,how='all').dropna(how='all').reset_index(drop=True)

            dates = pd.to_datetime(df[df.columns[0]],errors='coerce').dropna()
            if dates.empty:
                years = df[df.columns[0]].astype(str).str.extract(re_year,expand=True)[0].dropna()
                months = df[df.columns[0]].astype(str).str.extract(re_month,expand=True, flags=re.IGNORECASE)[0].dropna()
                if years.empty or months.empty:
                    raise('Date not found')

                year=int(years.iloc[-1])
                month = months.iloc[-1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                day = last_day_month(year=year, month=month)          
                date_formated = format_date(f"{year}-{month}-{day}")
            else:
                date_formated = dates.iloc[-1] + pd.offsets.MonthEnd()

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

Executor_D_BO_000000463 = D_BO_000000463
Robot = D_BO_000000463
