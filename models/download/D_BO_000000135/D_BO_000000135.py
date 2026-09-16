from models.download.Download_Base import Download_Base
import sys, re, os, urllib
import urllib.parse
sys.path.append("..")
import pandas as pd
from models.download.tools.download_tools import format_date, month_abr_to_number,month_to_number,last_day_month, delete_hidden_sheets
from models.download.BCB_Boletin_Mensual import BCB_Boletin_Mensual

class D_BO_000000135(BCB_Boletin_Mensual):

    def get_file_url(self, main_url, updated_to, key_words = "caja ahorro no bancarias",format='%Y-%m-%d'):
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
        files_urls = super().get_file_url_main(main_url=main_url,updated_to=updated_to, key_words=key_words, exact=False)
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
        help_dict = {}
        # Iterate over each file path
        for file in files_paths:
            parsed_url = urllib.parse.urlparse(file['download_url'])
            root_url = os.path.dirname(parsed_url.path)
            file_name = os.path.basename(parsed_url.path)
            extension = os.path.splitext(file_name)[1].replace(".","")
            

            re_date = r"(\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b).*(\b\d{4})\s*[(]?p?[)]?"
            print(f"Comparing file: {file['tmp_path']}")

            if 'pdf' in extension:
                help_dict[root_url] = {extension:file}
                continue
                        
            delete_hidden_sheets(file=file["tmp_path"])
            
            # Extract date from the file
            df_new_file = pd.read_excel(file["tmp_path"],header=[1])
            for column in df_new_file.columns:
                if df_new_file[column].isna().all():
                    df_new_file.drop(columns=[column], inplace=True)
            
            dataframe_to_look = df_new_file.iloc[:10]
            matches = []
            for column in dataframe_to_look.columns:
                for index, value in dataframe_to_look[column].items():
                    # Convert the value to lowercase and strip whitespace
                    value_str = str(value).strip().lower()
                    # Search for matches of the date pattern in the value string    
                    match_value = re.search(re_date,value_str)
                    if match_value :
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
        files_dicts_with_pdfs = []
        
        for file in files_dicts:
            parsed_url = urllib.parse.urlparse(file['download_url'])
            root_url = os.path.dirname(parsed_url.path)
            if 'pdf' in help_dict.get(root_url, {}):
                pdf_file = help_dict[root_url]['pdf']
                pdf_file["updated_to"] = file["updated_to"]
                files_dicts_with_pdfs.append(pdf_file)
            files_dicts_with_pdfs.append(file)
        print(len(files_dicts_with_pdfs))
        return files_dicts_with_pdfs
    
# if __name__ == "__main__":
#     robot = D_BO_000000135()
#     # x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=pub_boletin-estadistico",updated_to="2023-10-21")
#     # print(len(x))
#     # print(x)
#     files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': r"\\10.0.0.9\SPIM\BCB\01-Informacion Estadistica\03-Sector Bancario y Financiero\03-Financiamiento concedido por\03-Sistema Bancario al Sector Privado por Sectores Económicos y Bancos\tmp\2024-05-07_11561103.03.xlsx"}]
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000135 = D_BO_000000135
Robot = D_BO_000000135
