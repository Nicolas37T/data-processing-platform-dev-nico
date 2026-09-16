from models.download.Download_Base import Download_Base
import sys, re, os, urllib
import urllib.parse
sys.path.append("..")
from models.download.tools.download_tools import format_date, month_abr_to_number,month_to_number,last_day_month, text_extract
from models.download.BCB_Boletin_Mensual import BCB_Boletin_Mensual

class D_BO_000000268(BCB_Boletin_Mensual):

    def get_file_url(self, main_url, updated_to, key_words = "transferencias unilaterales",format='%Y-%m-%d'):
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
        help_dict = {}
        # Iterate over each file path
        for file in files_paths:
            
            parsed_url = urllib.parse.urlparse(file['download_url'])
            root_url = os.path.dirname(parsed_url.path)
            file_name = os.path.basename(parsed_url.path)
            extension = os.path.splitext(file_name)[1].replace(".","")

            re_year = r'(^\b\d{4})\s*[(]?p?[)]?'
            re_month = r'-((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))'
            print(f"Comparing file: {file['tmp_path']}")
            
            if not 'pdf' in extension:
                help_dict[root_url] = {"xlsx":file}
                continue

            lines = text_extract(file["tmp_path"])
            
            years = [re.search(re_year, line,re.IGNORECASE).group(1) for line in lines if re.search(re_year, line,re.IGNORECASE)]
            months = [re.search(re_month, line,re.IGNORECASE) for line in lines if re.search(re_month, line,re.IGNORECASE)]
            
            year = int(sorted(years)[-1])
            if months:
                month= months[-1].group(1)
                month = month_to_number(month) if month_to_number(month) else month_abr_to_number(month)
            else:
                month=12
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
            if 'xlsx' in help_dict.get(root_url, {}):
                xlsx_file = help_dict[root_url]['xlsx']
                xlsx_file["updated_to"] = file["updated_to"]
                files_dicts_with_pdfs.append(xlsx_file)
            files_dicts_with_pdfs.append(file)
        print(len(files_dicts_with_pdfs))
        return files_dicts_with_pdfs
    
# if __name__ == "__main__":
#     robot = D_BO_000000268()
#     # x = robot.get_file_url(main_url="https://www.bcb.gob.bo/?q=pub_boletin-mensual",updated_to="2024-1-21")
#     # print(len(x))
#     # print(x)
#     files = []
#     y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     print(y)

Executor_D_BO_000000268 = D_BO_000000268
Robot = D_BO_000000268
