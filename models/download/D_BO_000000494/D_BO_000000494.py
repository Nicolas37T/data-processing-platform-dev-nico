from models.download.Download_Base import Download_Base
import traceback
import re
import os
import zipfile
import pandas as pd
from datetime import datetime
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number, text_extract
from models.download.CNDC import CNDC

class D_BO_000000494(CNDC):

    def get_file_url(self, main_url, updated_to,key_words="oferta potencia" , format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        return self.get_file_url_main(main_url=main_url,updated_to=updated_to,key_words=key_words)

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
        re_date2 = r"(\d{1,2}\/\d{1,2}\/\d{2})"

        # Iterate over each file path
        for file in files_paths:
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            print(f"Comparing file: {file['tmp_path']}")

            try:
                if "zip" in extension:
                    folder_path = os.path.dirname(file['tmp_path'])
                    extract_dir = os.path.join(folder_path,os.path.splitext(file_name)[0])
                    
                    with zipfile.ZipFile(file['tmp_path'], 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            # Normalizar las rutas dentro del archivo ZIP
                            member_path = member.filename.replace('\\', '/')
                            member.filename = member_path

                            # Extraer el miembro con la ruta normalizada
                            zip_ref.extract(member, extract_dir)
                    while True:
                        new_file_name = os.listdir(extract_dir)[0]
                        extract_dir = os.path.join(extract_dir,new_file_name)
                        
                        if os.path.isfile(extract_dir):
                            break
                    file['zip_path'] = file['tmp_path']
                    file['tmp_path'] = extract_dir
            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                continue

            # Extract date from the file
            print("Extracting date from the file...")
            file_name = os.path.basename(file['tmp_path'])
            extension = os.path.splitext(file_name)[1]
            if 'pdf' in extension:
                text = " ".join(text_extract(file["tmp_path"]))

                match2 = re.search(re_date2, text, re.IGNORECASE)
                match1 = re.search(re_date, text, re.IGNORECASE)
                if match2:
                    date_formated = format_date(match2.group(1), format="%d/%m/%y")
                elif match1:
                    date = match1.groups()
                    month = month_to_number(date[1]) or month_abr_to_number(date[1])
                    date_formated = format_date(f"{date[2]}-{month}-{date[0]}")
                else:
                    date_formated = None
            else:    
                df_new_file = pd.read_excel(file["tmp_path"])

                for column in df_new_file.columns:
                    if df_new_file[column].isna().all():
                        df_new_file.drop(columns=[column], inplace=True)
                
                col = df_new_file.stack().astype(str)

                date = col.str.extract(re_date2, flags=re.IGNORECASE).dropna()
                if not date.empty:
                    date_formated = format_date(date[0].iloc[0],format="%d/%m/%y")

                elif not col.str.extract(re_date, flags=re.IGNORECASE).dropna().empty:
                    date = col.str.extract(re_date, flags=re.IGNORECASE).dropna().iloc[0]
                    month = month_to_number(date[1]) or month_abr_to_number(date[1])
                    date_formated = format_date(f"{date[2]}-{month}-{date[0]}")

                else:
                    parsed = pd.to_datetime(col, errors="coerce").dropna()
                    date_formated = parsed.iloc[0] if not parsed.empty else None

            # Skip the file if a valid date could not be extracted
            if not isinstance(date_formated, (datetime, pd.Timestamp)):
                print(f"Could not extract a valid date from file {file_name} (got: {date_formated!r}). Skipping...")
                continue

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

Executor_D_BO_000000494 = D_BO_000000494
Robot = D_BO_000000494
