from models.download.Download_Base import Download_Base
from models.download.ASFI import ASFI

class D_BO_000000327(ASFI):

    def get_file_url(self, main_url, updated_to,format='%Y-%m-%d'):
        """
        Extracts download URLs for files dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            format (str, optional): Date format to parse 'updated_to'. Defaults to '%Y-%m-%d'.

        Returns:
            list: A list of download URLs for files that meet the criteria.
        """
        # Call the superclass method to get a list of file URLs from the main page 
        files_urls = super().get_file_url_main(main_url=main_url,updated_to=updated_to,SECTION=r"agencia",KEY_WORDS=r"agencia")
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
        # Call the superclass method to get a list of dictionaries with information about files that meet the criteria
        files_dicts = super().compare_files_main(files_paths=files_paths, updated_to=updated_to, RE_DATE=r'(\d{1,2})\D*((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic))\D*(\d{4})',SHEET=-1,TYPE=1)
        return files_dicts

Executor_D_BO_000000327 = D_BO_000000327
Robot = D_BO_000000327
