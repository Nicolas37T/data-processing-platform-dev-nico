from models.download.Download_Base import Download_Base
from models.download.BCRP import BCRP

class D_PE_000000002(BCRP):

    def check_new_data(self, main_url, updated_to,path,key_words, format='%Y-%m-%d'):
        """
        Extracts data from the main_url dated after update_to date.

        Parameters:
            main_url (str): The URL of the main page.
            updated_to (str): The latest date for which the database contains records.
            path (str): The directory path to store temporary files.
            key_words (str): A string used to name the CSV file.
            format (str): The format of the dates. Default is '%Y-%m-%d'.

        Returns:
            list: A list of dictionaries containing information about the extracted data.
        """
        series_list = ['PD31887XD', 'PD31888XD', 'PD31889XD']
        return self.main_check_new_data(series_list=series_list, main_url=main_url, updated_to=updated_to, path=path, key_words=key_words)

Executor_D_PE_000000002 = D_PE_000000002
Robot = D_PE_000000002
