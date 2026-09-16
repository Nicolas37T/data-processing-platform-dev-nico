from models.download.Download_Base import Download_Base
import os, zipfile
from models.download.tools.download_tools import format_date, month_to_number, month_abr_to_number, last_day_month, read_excel
from models.download.CNDC import CNDC

class D_BO_000000065(CNDC):

    def get_file_url(self, main_url, updated_to,key_words="cargos retiros" , format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        return self.get_file_url_main(main_url=main_url,updated_to=updated_to,key_words=key_words,frecuency='mensual')

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
            re_date = r"((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\s*\w*\s*(\d{4})"
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
            df_new_file = df_new_file.dropna(axis=1, how='all')
            
            date = df_new_file.astype(str).stack().str.extract(re_date, expand=False).dropna().iloc[0]
            print(date)
            
            year = int(date[1])
            month = date[0]
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
#     robot = D_BO_000000065()
#     x = robot.get_file_url(main_url="https://www.cndc.bo/estadisticas/mensual.php",updated_to="2023-11-21")
#     print(x)
#     # y = robot.compare_files(files_paths=[{"tmp_path": r"C:\Users\Kevin Padilla\Downloads\iny_dia_1223.zip"}],updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000065 = D_BO_000000065
Robot = D_BO_000000065
