from models.download.Download_Base import Download_Base
import traceback
import re
import os
import zipfile
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number, month_to_number
from models.download.CNDC import CNDC

class D_BO_000000488(CNDC):

    def get_file_url(self, main_url, updated_to, key_words="indisponibilidad", format='%Y-%m-%d'):
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
        re_date2 = r"(\d{4}.?\d{1,2}.?\d{1,2})"

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
            
            df_new_file = pd.read_excel(file["tmp_path"])

            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            date = df_new_file[df_new_file.columns[0]].str.extract(re_date,flags=re.IGNORECASE,expand=True).dropna()
            if date.empty:
                date = df_new_file[df_new_file.columns[0]].astype(str).str.extract(re_date2,flags=re.IGNORECASE).dropna().iloc[0]
                date_formated = format_date(date[0])
            else:
                date = date.iloc[0]
                month = date[1]
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
                date_formated = format_date(f"{date[2]}-{month}-{date[0]}")
            
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
#     robot = Executor_D_BO_000000488()
    # x =robot.get_file_url(main_url="https://www.cndc.bo/estadisticas/index.php",updated_to='2024-08-01')
    # print(len(x))
    # print(x)
    # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"/opt/airflow/models/download/D_BO_000000488/indp_140824.zip"}]
    # y = robot.compare_files(files_paths=files,updated_to="2024-08-09")
    # print(y)


Executor_D_BO_000000488 = D_BO_000000488
Robot = D_BO_000000488
