import sys
import re, os, traceback, time, shutil
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pandas as pd
from models.download.tools.download_tools import format_date
from models.download.Download_Base import Download_Base

class D_BO_000000219(Download_Base):
    moneda_dict = {
        'argentina':1,
        'australia':41,
        'brasil':6,
        'canada':7,
        'chile':8,
        'colombia':9,
        'dinamarca':11,
        'ecuador':12,
        'usd_compra':34,
        'usd_venta':35,
        'euro':53,
        'inglaterra':33,
        'japon':20,
        'mexico':22,
        'noruega':23,
        'peru':25,
        'china_offshore':26,
        'suecia':30,
        'suiza':31,
        'ufv':76,
        'venezuela':43,
        'corea_sur':10,
        'hong_kong':16,
        'india':17,
        'paraguay':24,
        'singapur':32,
        'tailandia':37,
        'taiwan':38,
        'uruguay':42,
        'rusia':99
    }

    def get_data(self, main_url, path, updated_to,format='%Y-%m-%d'):
        """
        Extracts data from URLs for files dated after updated_to.

        Parameters:
            main_url (str): The URL of the main page.
            path (str): The path where files are stored.
            updated_to (str): The latest date for which the database contains records.
            format (str): The date format to use for the 'updated_to' field.

        Returns:
            str: A temporary path where the files were stored or an empty string if there are no files downloaded.
        """

        # Erase the previous tmp path and create the a new one
        with sync_playwright() as pl:
            # Convert updated_to string to datetime object
            updated_to = format_date(updated_to)
            # XPath to locate elements
            export_button_xpath = '//button[@type="submit"]'

            end_date = datetime.today()
            start_date = end_date - timedelta(weeks=1)
            end_date = end_date.strftime('%d-%m-%Y')
            start_date = start_date.strftime('%d-%m-%Y')

            # Erase the previous tmp path and create the a new one
            path = os.path.join(path, 'tmp')
            if os.path.exists(path):
                shutil.rmtree(path)
            os.makedirs(path)

            RETRIES = 10
            file_paths = []
            try:
                # Launch browser and navigate to main URL
                print(f"Launching browser and navigating to {main_url} ...")
                browser = pl.chromium.launch(headless=True)
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36')
                context.set_default_timeout(1000*60*5)
                page = context.new_page()
                print(self.moneda_dict.items())
                for moneda,moneda_id in self.moneda_dict.items():

                    for i in range(RETRIES):
                        try:
                            response = page.goto(f'https://deudaexternapublica.bcb.gob.bo/publico/tipos-cambio/historicos-resultados?idMoneda[]={moneda_id}&multiselect_idMoneda={moneda_id}&fechaInicial={start_date}&fechaFinal={end_date}',wait_until='domcontentloaded')

                            if not response and  not response.ok:
                                time.sleep(5)
                                continue

                            with page.expect_download() as download_info:
                                page.locator(export_button_xpath).click()

                            if download_info:
                                break                           
                        
                        except Exception as e:
                            print(f"Retrie for:{moneda}")
                            time.sleep(5)
                            continue
                            
                        time.sleep(5)
                    download = download_info.value
                    download_date = self.compare_files(file_path=download.path())
                    if download_date<=updated_to:
                        continue

                    download_date = download_date.strftime(format)
                    new_path = os.path.join(path,f"{download_date}_{moneda}.xls")
                    download.save_as(new_path)
                    file_paths.append({
                        "tmp_path": new_path})
                    time.sleep(2)
                
                if file_paths:
                    return path
                return ""                    

            except Exception as e:
                print(f"An error ocurred: {e}")
                traceback.print_exc()
                return []
            finally:
                # Close page and browser
                if 'page' in locals():
                    page.close()
                if 'browser' in locals():
                    browser.close()

    def compare_files(self, file_path, format='%Y-%m-%d'):
    
        re_date = r'(\d{4})\D(\d{1,2})\D(\d{1,2})'
        
        # Extract date from the file
        tables = pd.read_html(file_path)
        df_new_file = tables[0]
        
        for column in df_new_file.columns:
            if df_new_file[column].isna().all():
                df_new_file.drop(columns=[column], inplace=True)
        
        sub_set = list(df_new_file[df_new_file.columns[2]])
    
        dates = [re.search(re_date, line) for line in sub_set if re.search(re_date, line)]
        date = dates[-1].group(1,2,3)
        
        return format_date(f"{date[0]}-{date[1]}-{date[2]}")        
        
if __name__ == "__main__":
    robot = Executor_D_BO_000000219()
    x = robot.get_data(main_url="https://estadisticas.minsalud.gob.bo/Reportes_Dinamicos/Menu_rep_dinamicos.aspx",updated_to="2025-03-17",path=r"D:\DATAX\data-processing-platform\models\download\D_BO_000000219")
    print(x)
#     # y = robot.compare_files(file_path=r"\\10.0.0.9\spim\SNIS\Vigilancia Epidemiologica\05 Tuberculosis y Lepra\2022\or_tuberculosis lepra.xls", year=2022)
#     # print(y)

Executor_D_BO_000000219 = D_BO_000000219
Robot = D_BO_000000219
