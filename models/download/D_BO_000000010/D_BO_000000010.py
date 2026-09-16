from models.download.Download_Base import Download_Base
from models.download.tools.download_tools import format_date
from models.download.ASFI_Agencias_Bolsa import ASFI_Agencias_Bolsa

class D_BO_000000010(ASFI_Agencias_Bolsa):

    def get_file_url(self, main_url, updated_to, key_words = "10 cartera agencias",format='%Y-%m-%d'):
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
        # Convert the updated_to date string to a date object using the specified format
        updated_to = format_date(updated_to)
            
        # Call the superclass method to get a list of file URLs from the main page    
        files_urls = super().get_file_url_main(main_url=main_url, key_words=key_words)
        return files_urls

Executor_D_BO_000000010 = D_BO_000000010
Robot = D_BO_000000010
