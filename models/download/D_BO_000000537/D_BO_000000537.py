import re
import time
import os
import traceback
import requests 
import shutil
import pandas as pd
from datetime import datetime, timedelta
from models.download.tools.download_tools import format_date, last_day_month
from models.download.Download_Base import Download_Base

class D_BO_000000537(Download_Base):

    def download_tmp(self,path, item, format='%Y-%m-%d'):
        
        """
        Downloads files from the specified URLs and saves them to the specified path.

        Parameters:
            path (str): The base path where files will be saved.
            file (dict): A dictionary containing the file details (URLs, code, updated date).

        Returns:
            list: A list of dictionaries with download URLs and file paths.
        """       
        
        
        # Download the ER file
        response, info, date = item
        date = date.strftime(format) 
        file_path = os.path.join(path,f"{date}_{info['cRegistro']}_{datetime.now().strftime('%Y%m%d')}.csv")
        with open(file_path, "wb") as f:
            f.write(response.content)
        df = pd.read_csv(file_path, sep=';')

        df.insert(loc=0, column='titulo2', value=info['tRegistro'] if info['tRegistro'] else 'sin titulo')
        df.insert(loc=0, column='titulo1', value=info['tTipoRegistro'] if info['tTipoRegistro'] else 'sin titulo')

        df.insert(loc=len(df.columns)-1, column='fecha', value=date)
        
        df.to_csv(file_path, sep=';',index=False)
        
    def get_data(self, main_url, path, updated_to, format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated in the present year.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """
        re_date = r'^(\d{4}\D\d{1,2}\D\d{1,2})'
        tipo_registros_codes = [302,317,301]
        seguros_codes_in_intervencion = [51954,51969] #Seguros Provida S.A.   (En intervención) y Bupa
        

        # Get the last year downloaded from the directory
        # Convert updated_to string to datetime object
        updated_to = format_date(updated_to)
        today = datetime.today()
        current_date = updated_to
        dates = []
        while current_date <= today:
            next_month = current_date + timedelta(days=15)
            last_day = last_day_month(year=next_month.year, month=next_month.month )
            current_date = next_month.replace(day=last_day)
            dates.append(current_date)        

        # Create the directory structure to save files
        new_file_path = os.path.join(path, 'tmp')
        if os.path.exists(new_file_path):
            shutil.rmtree(new_file_path)
        os.makedirs(new_file_path)        
        
        try:
            data = []
            for code in tipo_registros_codes:
                tipo_registro_endpoint = f'https://api.aps.gob.bo/aps.web/rms/entidades?cTipoRegistro={code}'
                response = requests.get(tipo_registro_endpoint)
                
                if not (200 <= response.status_code < 300):
                    raise ValueError(f'Broken endpoint: {tipo_registro_endpoint}')
                response_data = response.json()
                data.extend(response_data['data'])
            data = [item for item in data if item['cRegistro'] not in seguros_codes_in_intervencion]
            
            entities_data = []
            for item in data:
                registro_endpoint = f'https://api.aps.gob.bo/aps.web/rms/registro?cRegistro={item["cRegistro"]}'

                response = requests.get(registro_endpoint)
                if not (200 <= response.status_code < 300):
                    raise ValueError(f'Broken endpoint: {tipo_registro_endpoint}')
            
                response_data = response.json()
                entities_data.append(response_data['data'])
            
            for date in dates:
                files_urls = []                
                for item in entities_data:
                    download_url = f'https://api.aps.gob.bo/aps.web/rms/cuentas-csv?entidad={item["codigo"]}&fInformacion={date.strftime(format="%Y%m%d")}'
                    response = requests.get(download_url,headers=self.headers)

                    if not (200 <= response.status_code < 300) or (len(response.content.strip())<10):
                        print(f'No data for {item["tRegistro"]} {date.strftime(format)}')
                        files_urls = []
                        break
                    files_urls.append((response,item,date))
                    time.sleep(1)
                if files_urls:
                    print(f'Downloading data for: {date.strftime(format)}')
                    files_urls = [self.download_tmp(path=new_file_path, item=f) for f in files_urls ]
            
            list_dates_downloaded = set([date.group(1) for f in os.listdir(new_file_path) if (date:= re.search(re_date,f))])
            
            if list_dates_downloaded:
                list_dates_downloaded = sorted(list(list_dates_downloaded))
                last_date = format_date(list_dates_downloaded[0])
                current_date = format_date(f'{last_date.year-1}-11-30')

                last_year_dates = []
                while True:
                    next_month = current_date + timedelta(days=15)
                    last_day = last_day_month(year=next_month.year, month=next_month.month )
                    current_date = next_month.replace(day=last_day)
                    if current_date >=last_date:
                        break
                    last_year_dates.append(current_date)
                
                files_urls = []                
                for date in last_year_dates:
                    for item in entities_data:
                        download_url = f'https://api.aps.gob.bo/aps.web/rms/cuentas-csv?entidad={item["codigo"]}&fInformacion={date.strftime(format="%Y%m%d")}'
                        response = requests.get(download_url,headers=self.headers)

                        if 200 <= response.status_code < 300:
                            files_urls.append((response,item,date))
                            time.sleep(1)
                
                if files_urls:
                    files_urls = [self.download_tmp(path=new_file_path, item=f) for f in files_urls ]

                return new_file_path
            
            print(f'There are not files after: {updated_to.strftime(format)}')
            return ''
        except Exception as e:
            print(f"An error ocurred: {e}")
            traceback.print_exc()
            return []
        
    
# if __name__ == "__main__":
#     robot = Executor_D_BO_000000537()
#     x = robot.get_data(main_url="https://www.bbv.com.bo/estados-financieros-por-emisor",path=r"D:\DATAX\data-processing-platform\models\download\D_BO_000000537", updated_to='2024-09-30')
    # print(len(x))
    # print(x)
#     # files = [{'download_url': 'https://www.bcb.gob.bo/webdocs/publicacionesbcb/2024/04/10/01.01P.xlsx', 'tmp_path': '\\\\10.0.0.9\\spim\\INE\\ESTADISTICAS ECONOMICAS\\SALARIOS Y REMUNERACIONES\\SECTOR PRIVADO\\02_Grupo Ocupacional\\tmp\\2024-05-13_155615download.xlsx'}]
#     # y = robot.compare_files(files_paths=files,updated_to="2023-01-21")
#     # print(y)

Executor_D_BO_000000537 = D_BO_000000537
Robot = D_BO_000000537
