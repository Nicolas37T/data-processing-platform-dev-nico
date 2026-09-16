from models.download.Download_Base import Download_Base
import os
import shutil
import asyncio
from models.download.DATASUR import DATASUR

class D_BO_000000522(DATASUR):

    def get_data(self, main_url,path,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """
        COUNTRY = "Bolivia"
        USER = "DATA_SUR_BORIS_USERNAME"
        PASSWORD = "DATA_SUR_BORIS_PASSWORD"
        YEAR = 2024
        RETRIES = 5
        
        path = os.path.join(path, 'tmp')
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
        
        tmp_path = None
        for i in range(RETRIES):
            if i == 0:
                tmp_path = asyncio.run(self.get_data_main(main_url=main_url, country_path=path, user=USER, password=PASSWORD, country=COUNTRY, year_flag=YEAR))
            else:
                tmp_path = asyncio.run(self.get_data_main(main_url=main_url, country_path=path, user=USER, password=PASSWORD, country=COUNTRY, year_flag=YEAR, resume=True))
            
            if tmp_path: 
                break   

        return tmp_path

Executor_D_BO_000000522 = D_BO_000000522
Robot = D_BO_000000522
